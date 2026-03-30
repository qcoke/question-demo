import random

from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import AttemptAnswer, Question, QuizAttempt


TEST_SIZE = 10


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

    return redirect("test_question", attempt_id=attempt.id, order=1)


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

    if request.method == "POST":
        selected_option = request.POST.get("selected_option")
        if selected_option not in {"A", "B", "C", "D"}:
            return render(request, "quiz/invalid_request.html")

        if answer_item.selected_option is not None:
            return redirect("test_question", attempt_id=attempt.id, order=next_order)

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

        next_order = get_next_unanswered_order(attempt)
        if next_order is None:
            finalize_attempt(attempt)
            return redirect("test_result", attempt_id=attempt.id)

        return redirect("test_question", attempt_id=attempt.id, order=next_order)

    if answer_item.shown_at is None:
        answer_item.shown_at = timezone.now()
        answer_item.save(update_fields=["shown_at"])

    progress = int(((order - 1) / attempt.total_questions) * 100)
    return render(
        request,
        "quiz/test.html",
        {
            "attempt": attempt,
            "answer_item": answer_item,
            "order": order,
            "total": attempt.total_questions,
            "progress": progress,
        },
    )


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
