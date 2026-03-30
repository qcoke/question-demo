import random

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .models import Question


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
    return render(
        request,
        "quiz/test.html",
        {"questions": selected_questions},
    )


def submit_test(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return render(request, "quiz/invalid_request.html")

    question_ids = request.POST.getlist("question_ids")
    questions = list(Question.objects.filter(id__in=question_ids).order_by("id"))

    total = len(questions)
    correct_count = 0
    review_items = []

    for question in questions:
        user_answer = request.POST.get(f"question_{question.id}")
        is_correct = user_answer == question.correct_option
        if is_correct:
            correct_count += 1

        review_items.append(
            {
                "question": question,
                "user_answer": user_answer,
                "is_correct": is_correct,
            }
        )

    score = int((correct_count / total) * 100) if total else 0
    return render(
        request,
        "quiz/result.html",
        {
            "score": score,
            "total": total,
            "correct_count": correct_count,
            "review_items": review_items,
        },
    )
