import random

from django.core.management.base import BaseCommand

from quiz.models import Question


class Command(BaseCommand):
    help = "初始化 20 以内加减法单选题题库"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="先清空题库再重新生成",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            deleted_count, _ = Question.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"已清空 {deleted_count} 道旧题"))

        created_count = 0

        for left in range(0, 21):
            for right in range(0, 21):
                # 加法结果保持在 20 以内
                if left + right <= 20:
                    created_count += self._create_question(left, right, "+")

                # 减法结果保持在 0 到 20 之间
                if left - right >= 0:
                    created_count += self._create_question(left, right, "-")

        total = Question.objects.count()
        self.stdout.write(self.style.SUCCESS(f"初始化完成，本次新增 {created_count} 道，题库共 {total} 道"))

    def _create_question(self, left: int, right: int, operator: str) -> int:
        if operator == "+":
            answer = left + right
        else:
            answer = left - right

        stem = f"{left} {operator} {right} = ?"
        options, correct_option = self._build_options(answer)

        _, created = Question.objects.get_or_create(
            stem=stem,
            defaults={
                "option_a": options[0][1],
                "option_b": options[1][1],
                "option_c": options[2][1],
                "option_d": options[3][1],
                "correct_option": correct_option,
            },
        )
        return 1 if created else 0

    def _build_options(self, answer: int):
        wrong_answers = set()
        while len(wrong_answers) < 3:
            delta = random.choice([1, 2, 3, 4, 5])
            candidate = answer + random.choice([-delta, delta])
            if 0 <= candidate <= 20 and candidate != answer:
                wrong_answers.add(candidate)

        candidates = [answer, *list(wrong_answers)]
        random.shuffle(candidates)

        labels = ["A", "B", "C", "D"]
        options = [(labels[idx], str(value)) for idx, value in enumerate(candidates)]

        correct_label = None
        for label, value in options:
            if int(value) == answer:
                correct_label = label
                break

        return options, correct_label
