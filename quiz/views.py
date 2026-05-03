import logging
import random

from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import AttemptAnswer, Question, QuizAttempt


TEST_SIZE = 10
LOG = logging.getLogger(__name__)


def start_test(request: HttpRequest) -> HttpResponse:
    questions = list(Question.objects.all())
    if len(questions) < TEST_SIZE:
        return render(
            request,
            "quiz/not_enough_questions.html",
            {"required": TEST_SIZE, "current": len(questions)},
        )

    selected_questions = random.sample(questions, TEST_SIZE)
    with transaction.atomic():
        attempt = QuizAttempt.objects.create(total_questions=TEST_SIZE)
        AttemptAnswer.objects.bulk_create(
            [
                AttemptAnswer(attempt=attempt, question=question, order=index)
                for index, question in enumerate(selected_questions, start=1)
            ]
        )

    first_item = attempt.answers.select_related("question").order_by("order").first()
    if first_item is not None:
        mark_question_shown(first_item)

    return render(request, "quiz/test.html", {"quiz_data": build_attempt_payload(attempt)})


def test_question(request: HttpRequest, attempt_id: int, order: int) -> HttpResponse:
    attempt = get_object_or_404(QuizAttempt, id=attempt_id)
    if attempt.finished_at:
        return redirect("test_result", attempt_id=attempt.id)

    next_order = get_next_unanswered_order(attempt)
    if next_order is None:
        finalize_attempt(attempt)
        return redirect("test_result", attempt_id=attempt.id)

    if order != next_order:
        return redirect("test_question", attempt_id=attempt.id, order=next_order)

    answer_item = get_object_or_404(
        AttemptAnswer.objects.select_related("question"),
        attempt=attempt,
        order=order,
    )
    mark_question_shown(answer_item)

    return render(
        request,
        "quiz/test.html",
        {"quiz_data": build_attempt_payload(attempt, current_order=order)},
    )


@require_POST
def submit_answer(request: HttpRequest, attempt_id: int) -> JsonResponse:
    raw_order = request.POST.get("order")
    raw_option = request.POST.get("selected_option")
    client_ip = request.META.get("REMOTE_ADDR", "-")
    LOG.info(
        "submit_answer received attempt_id=%s order=%r selected_option=%r from %s",
        attempt_id, raw_order, raw_option, client_ip,
    )

    with transaction.atomic():
        attempt = get_object_or_404(QuizAttempt.objects.select_for_update(), id=attempt_id)

        if attempt.finished_at:
            LOG.info("submit_answer attempt_id=%s already finished", attempt_id)
            return JsonResponse(
                {
                    "ok": False,
                    "error": "attempt_finished",
                    "result": build_result_payload(attempt),
                },
                status=409,
            )

        try:
            order = int(raw_order or "")
        except (TypeError, ValueError):
            LOG.warning("submit_answer attempt_id=%s invalid_order=%r", attempt_id, raw_order)
            return JsonResponse({"ok": False, "error": "invalid_order"}, status=400)

        selected_option = raw_option
        if selected_option not in {"A", "B", "C", "D"}:
            LOG.warning(
                "submit_answer attempt_id=%s order=%s rejected invalid_option=%r",
                attempt_id, order, selected_option,
            )
            return JsonResponse({"ok": False, "error": "invalid_option"}, status=400)

        next_order = get_next_unanswered_order(attempt)
        if next_order is None:
            finalize_attempt(attempt)
            LOG.info("submit_answer attempt_id=%s finished during submit", attempt_id)
            return JsonResponse(
                {
                    "ok": False,
                    "error": "attempt_finished",
                    "result": build_result_payload(attempt),
                },
                status=409,
            )

        if order != next_order:
            LOG.warning(
                "submit_answer attempt_id=%s out_of_order received=%s expected=%s",
                attempt_id, order, next_order,
            )
            return JsonResponse(
                {"ok": False, "error": "out_of_order", "current_order": next_order},
                status=409,
            )

        answer_item = get_object_or_404(
            AttemptAnswer.objects.select_related("question"),
            attempt=attempt,
            order=order,
        )
        mark_question_shown(answer_item)

        answered_at = timezone.now()
        shown_at = answer_item.shown_at or answered_at
        elapsed = max(0, int((answered_at - shown_at).total_seconds()))

        answer_item.selected_option = selected_option
        answer_item.is_correct = selected_option == answer_item.question.correct_option
        answer_item.answered_at = answered_at
        answer_item.time_spent_seconds = elapsed
        answer_item.save(
            update_fields=[
                "selected_option",
                "is_correct",
                "answered_at",
                "time_spent_seconds",
            ]
        )
        LOG.info(
            "submit_answer attempt_id=%s order=%s saved option=%s correct=%s elapsed=%ss",
            attempt_id, order, selected_option, answer_item.is_correct, elapsed,
        )

        next_order = get_next_unanswered_order(attempt)
        if next_order is None:
            finalize_attempt(attempt)
            LOG.info(
                "submit_answer attempt_id=%s completed score=%s correct=%s/%s",
                attempt_id, attempt.score, attempt.correct_count, attempt.total_questions,
            )
            return JsonResponse(
                {
                    "ok": True,
                    "completed": True,
                    "result": build_result_payload(attempt),
                }
            )

        next_item = get_object_or_404(
            AttemptAnswer.objects.select_related("question"),
            attempt=attempt,
            order=next_order,
        )
        mark_question_shown(next_item)

        return JsonResponse({"ok": True, "completed": False, "current_order": next_order})


def test_result(request: HttpRequest, attempt_id: int) -> HttpResponse:
    attempt = get_object_or_404(QuizAttempt, id=attempt_id)
    if not attempt.finished_at:
        return render(request, "quiz/invalid_request.html")

    review_items = attempt.answers.select_related("question").all()
    return render(
        request,
        "quiz/result.html",
        {
            "attempt": attempt,
            "review_items": review_items,
        },
    )


def finalize_attempt(attempt: QuizAttempt) -> None:
    if attempt.finished_at:
        return

    total = attempt.answers.count()
    correct_count = attempt.answers.filter(is_correct=True).count()
    score = int((correct_count / total) * 100) if total else 0

    finished_at = timezone.now()
    duration_seconds = max(0, int((finished_at - attempt.created_at).total_seconds()))

    attempt.correct_count = correct_count
    attempt.score = score
    attempt.finished_at = finished_at
    attempt.duration_seconds = duration_seconds
    attempt.save(update_fields=["correct_count", "score", "finished_at", "duration_seconds"])


def get_next_unanswered_order(attempt: QuizAttempt) -> int | None:
    return (
        attempt.answers.filter(selected_option__isnull=True)
        .order_by("order")
        .values_list("order", flat=True)
        .first()
    )


def mark_question_shown(answer_item: AttemptAnswer) -> None:
    if answer_item.shown_at is None:
        answer_item.shown_at = timezone.now()
        answer_item.save(update_fields=["shown_at"])


def build_attempt_payload(attempt: QuizAttempt, current_order: int | None = None) -> dict:
    answer_items = list(attempt.answers.select_related("question").order_by("order"))
    active_order = current_order or get_next_unanswered_order(attempt) or 1

    return {
        "attemptId": attempt.id,
        "total": attempt.total_questions,
        "currentOrder": active_order,
        "submitUrl": reverse("submit_answer", kwargs={"attempt_id": attempt.id}),
        "resultUrl": reverse("test_result", kwargs={"attempt_id": attempt.id}),
        "questions": [build_client_question_payload(item) for item in answer_items],
    }


def build_client_question_payload(answer_item: AttemptAnswer) -> dict:
    return {
        "order": answer_item.order,
        "stem": answer_item.question.stem,
        "options": {
            "A": answer_item.question.option_a,
            "B": answer_item.question.option_b,
            "C": answer_item.question.option_c,
            "D": answer_item.question.option_d,
        },
    }


def build_result_payload(attempt: QuizAttempt) -> dict:
    review_items = list(attempt.answers.select_related("question").order_by("order"))
    return {
        "attemptId": attempt.id,
        "score": attempt.score,
        "correctCount": attempt.correct_count,
        "totalQuestions": attempt.total_questions,
        "durationSeconds": attempt.duration_seconds,
        "finishedAt": attempt.finished_at.isoformat() if attempt.finished_at else None,
        "reviewItems": [
            {
                "order": item.order,
                "stem": item.question.stem,
                "selectedOption": item.selected_option,
                "correctOption": item.question.correct_option,
                "isCorrect": item.is_correct,
                "timeSpentSeconds": item.time_spent_seconds,
            }
            for item in review_items
        ],
    }

