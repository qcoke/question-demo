from django.db import models


class Question(models.Model):
	OPTION_CHOICES = [
		("A", "A"),
		("B", "B"),
		("C", "C"),
		("D", "D"),
	]

	stem = models.CharField(max_length=100, unique=True)
	option_a = models.CharField(max_length=20)
	option_b = models.CharField(max_length=20)
	option_c = models.CharField(max_length=20)
	option_d = models.CharField(max_length=20)
	correct_option = models.CharField(max_length=1, choices=OPTION_CHOICES)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["id"]

	def __str__(self):
		return self.stem
