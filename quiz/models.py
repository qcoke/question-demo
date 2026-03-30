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


class QuizAttempt(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    total_questions = models.PositiveIntegerField(default=0)
    correct_count = models.PositiveIntegerField(default=0)
    score = models.PositiveIntegerField(default=0)
    duration_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"Attempt #{self.id}"


class AttemptAnswer(models.Model):
    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    question = models.ForeignKey(Question, on_delete=models.PROTECT)
    order = models.PositiveIntegerField()
    selected_option = models.CharField(
        max_length=1,
        choices=Question.OPTION_CHOICES,
        null=True,
        blank=True,
    )
    is_correct = models.BooleanField(default=False)
    shown_at = models.DateTimeField(null=True, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    time_spent_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        unique_together = ("attempt", "order")

    def __str__(self):
        return f"Attempt #{self.attempt_id} - Q{self.order}"
