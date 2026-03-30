from django.contrib import admin

from .models import AttemptAnswer, Question, QuizAttempt


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "stem", "correct_option", "created_at")
    search_fields = ("stem",)


class AttemptAnswerInline(admin.TabularInline):
    model = AttemptAnswer
    extra = 0
    can_delete = False
    readonly_fields = (
        "order",
        "question",
        "selected_option",
        "is_correct",
        "shown_at",
        "answered_at",
        "time_spent_seconds",
    )


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "created_at",
        "finished_at",
        "total_questions",
        "correct_count",
        "accuracy_rate",
        "score",
        "duration_display",
    )
    list_filter = ("created_at", "finished_at")
    date_hierarchy = "created_at"
    search_fields = ("id",)
    readonly_fields = (
        "created_at",
        "finished_at",
        "total_questions",
        "correct_count",
        "score",
        "duration_seconds",
    )
    inlines = [AttemptAnswerInline]

    @admin.display(description="正确率")
    def accuracy_rate(self, obj: QuizAttempt) -> str:
        if obj.total_questions == 0:
            return "0%"
        rate = (obj.correct_count / obj.total_questions) * 100
        return f"{rate:.0f}%"

    @admin.display(description="总耗时")
    def duration_display(self, obj: QuizAttempt) -> str:
        minutes, seconds = divmod(obj.duration_seconds, 60)
        return f"{minutes}分{seconds}秒"


@admin.register(AttemptAnswer)
class AttemptAnswerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "attempt",
        "order",
        "question",
        "selected_option",
        "is_correct",
        "time_spent_seconds",
        "answered_at",
    )
    list_filter = ("is_correct", "selected_option", "attempt__created_at")
    readonly_fields = ("shown_at", "answered_at", "time_spent_seconds")
    search_fields = ("question__stem",)
