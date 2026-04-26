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

    def test_start_test_renders_single_page_bootstrap_data(self):
        response = self.client.get(reverse("start_test"))
        self.assertEqual(response.status_code, 200)

        attempt = QuizAttempt.objects.first()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.total_questions, 10)
        self.assertEqual(attempt.answers.count(), 10)
        self.assertIn("quiz_data", response.context)
        self.assertEqual(len(response.context["quiz_data"]["questions"]), 10)
        self.assertEqual(
            response.context["quiz_data"]["submitUrl"],
            reverse("submit_answer", kwargs={"attempt_id": attempt.id}),
        )
        self.assertEqual(attempt.answers.filter(shown_at__isnull=False).count(), 1)

    def test_ajax_submit_flow_scores_correctly(self):
        self.client.get(reverse("start_test"))

        attempt = QuizAttempt.objects.first()
        self.assertIsNotNone(attempt)

        answer_items = list(attempt.answers.select_related("question").order_by("order"))
        for idx, item in enumerate(answer_items, start=1):
            response = self.client.post(
                reverse("submit_answer", kwargs={"attempt_id": attempt.id}),
                {"order": item.order, "selected_option": item.question.correct_option},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()

            if idx < len(answer_items):
                self.assertFalse(payload["completed"])
                self.assertEqual(payload["current_order"], item.order + 1)
            else:
                self.assertTrue(payload["completed"])
                self.assertEqual(payload["result"]["score"], 100)
                self.assertEqual(payload["result"]["correctCount"], 10)
                self.assertEqual(len(payload["result"]["reviewItems"]), 10)

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

    def test_submit_rejects_future_order(self):
        self.client.get(reverse("start_test"))
        attempt = QuizAttempt.objects.first()
        self.assertIsNotNone(attempt)

        response = self.client.post(
            reverse("submit_answer", kwargs={"attempt_id": attempt.id}),
            {"order": 5, "selected_option": "A"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json(),
            {"ok": False, "error": "out_of_order", "current_order": 1},
        )

    def test_cannot_resubmit_answered_question(self):
        self.client.get(reverse("start_test"))
        attempt = QuizAttempt.objects.first()
        self.assertIsNotNone(attempt)

        first_item = attempt.answers.select_related("question").get(order=1)
        self.client.post(
            reverse("submit_answer", kwargs={"attempt_id": attempt.id}),
            {"order": 1, "selected_option": first_item.question.correct_option},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        retry_response = self.client.post(
            reverse("submit_answer", kwargs={"attempt_id": attempt.id}),
            {"order": 1, "selected_option": "B"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(retry_response.status_code, 409)
        self.assertEqual(
            retry_response.json(),
            {"ok": False, "error": "out_of_order", "current_order": 2},
        )

        first_item.refresh_from_db()
        self.assertEqual(first_item.selected_option, first_item.question.correct_option)

    def test_finished_attempt_can_render_result_page(self):
        self.client.get(reverse("start_test"))
        attempt = QuizAttempt.objects.first()
        self.assertIsNotNone(attempt)

        answer_items = list(attempt.answers.select_related("question").order_by("order"))
        for item in answer_items:
            self.client.post(
                reverse("submit_answer", kwargs={"attempt_id": attempt.id}),
                {"order": item.order, "selected_option": item.question.correct_option},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )

        result_response = self.client.get(reverse("test_result", kwargs={"attempt_id": attempt.id}))
        self.assertEqual(result_response.status_code, 200)
        self.assertContains(result_response, "测试结果")

