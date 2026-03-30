from django.test import TestCase
from django.urls import reverse

from .models import AttemptAnswer, Question, QuizAttempt


class QuizFlowTests(TestCase):
    def setUp(self):
        for i in range(10):
            Question.objects.create(
                stem=f"{i} + 0 = ?",
                option_a="0",
                option_b="1",
                option_c="2",
                option_d="3",
                correct_option="A",
            )

    def test_start_test_returns_ten_questions(self):
        response = self.client.get(reverse("start_test"))
        self.assertEqual(response.status_code, 302)

        attempt = QuizAttempt.objects.first()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.total_questions, 10)
        self.assertEqual(attempt.answers.count(), 10)

    def test_per_question_flow_scores_correctly(self):
        self.client.get(reverse("start_test"))

        attempt = QuizAttempt.objects.first()
        self.assertIsNotNone(attempt)

        answer_items = list(attempt.answers.select_related("question").order_by("order"))
        for item in answer_items:
            self.client.get(
                reverse("test_question", kwargs={"attempt_id": attempt.id, "order": item.order})
            )
            response = self.client.post(
                reverse("test_question", kwargs={"attempt_id": attempt.id, "order": item.order}),
                {"selected_option": item.question.correct_option},
            )
            self.assertEqual(response.status_code, 302)

        attempt.refresh_from_db()
        self.assertIsNotNone(attempt.finished_at)
        self.assertEqual(attempt.correct_count, 10)
        self.assertEqual(attempt.score, 100)
        self.assertGreaterEqual(attempt.duration_seconds, 0)

        self.assertEqual(
            AttemptAnswer.objects.filter(attempt=attempt, is_correct=True).count(),
            10,
        )
        self.assertEqual(
            AttemptAnswer.objects.filter(attempt=attempt, answered_at__isnull=False).count(),
            10,
        )

        result_response = self.client.get(
            reverse("test_result", kwargs={"attempt_id": attempt.id})
        )
        self.assertEqual(result_response.status_code, 200)

    def test_cannot_jump_to_future_question(self):
        self.client.get(reverse("start_test"))
        attempt = QuizAttempt.objects.first()
        self.assertIsNotNone(attempt)

        jump_response = self.client.get(
            reverse("test_question", kwargs={"attempt_id": attempt.id, "order": 5})
        )
        self.assertEqual(jump_response.status_code, 302)
        self.assertTrue(
            jump_response.url.endswith(
                reverse("test_question", kwargs={"attempt_id": attempt.id, "order": 1})
            )
        )

    def test_cannot_resubmit_answered_question(self):
        self.client.get(reverse("start_test"))
        attempt = QuizAttempt.objects.first()
        self.assertIsNotNone(attempt)

        first_item = attempt.answers.select_related("question").get(order=1)
        self.client.post(
            reverse("test_question", kwargs={"attempt_id": attempt.id, "order": 1}),
            {"selected_option": first_item.question.correct_option},
        )

        retry_response = self.client.post(
            reverse("test_question", kwargs={"attempt_id": attempt.id, "order": 1}),
            {"selected_option": "B"},
        )
        self.assertEqual(retry_response.status_code, 302)
        self.assertTrue(
            retry_response.url.endswith(
                reverse("test_question", kwargs={"attempt_id": attempt.id, "order": 2})
            )
        )

        first_item.refresh_from_db()
        self.assertEqual(first_item.selected_option, first_item.question.correct_option)
