from django.test import TestCase
from django.urls import reverse

from .models import Question


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
		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.context["questions"]), 10)

	def test_submit_test_scores_correctly(self):
		questions = list(Question.objects.all().order_by("id"))
		payload = {"question_ids": [str(q.id) for q in questions]}
		for question in questions:
			payload[f"question_{question.id}"] = "A"

		response = self.client.post(reverse("submit_test"), payload)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["correct_count"], 10)
		self.assertEqual(response.context["score"], 100)
