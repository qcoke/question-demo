import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from quiz.models import Question


class Command(BaseCommand):
    help = "从 JSON 文件导入单选题到题库"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default="questions.json",
            help="题库 JSON 文件路径（默认: questions.json）",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="导入前先清空题库",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file"]).expanduser().resolve()

        if not file_path.exists():
            raise CommandError(f"文件不存在: {file_path}")

        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"JSON 解析失败: {exc}") from exc

        if not isinstance(payload, list):
            raise CommandError("JSON 顶层必须是数组")

        if options["reset"]:
            deleted_count, _ = Question.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"已清空 {deleted_count} 道旧题"))

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for index, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                skipped_count += 1
                self.stdout.write(self.style.WARNING(f"第 {index} 条不是对象，已跳过"))
                continue

            stem = str(item.get("question", "")).strip()
            options_list = item.get("options")
            correct_answer = item.get("correct_answer")

            if not stem or not isinstance(options_list, list) or len(options_list) < 3:
                skipped_count += 1
                self.stdout.write(self.style.WARNING(f"第 {index} 条字段不完整，已跳过"))
                continue

            normalized_options = [str(options_list[0]), str(options_list[1]), str(options_list[2])]
            correct_answer_str = str(correct_answer)
            option_d = self._build_fourth_option(normalized_options, correct_answer_str)
            normalized_options.append(option_d)

            if correct_answer_str in normalized_options:
                correct_option = ["A", "B", "C", "D"][normalized_options.index(correct_answer_str)]
            else:
                # 理论上不会到这里，兜底保证写入后存在正确答案
                normalized_options[0] = correct_answer_str
                correct_option = "A"

            _, created = Question.objects.update_or_create(
                stem=stem,
                defaults={
                    "option_a": normalized_options[0],
                    "option_b": normalized_options[1],
                    "option_c": normalized_options[2],
                    "option_d": normalized_options[3],
                    "correct_option": correct_option,
                },
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        total_count = Question.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"导入完成: created={created_count}, updated={updated_count}, "
                    f"skipped={skipped_count}, total={total_count}"
                )
            )
        )

    def _build_fourth_option(self, options, correct_answer_str):
        if correct_answer_str and correct_answer_str not in options:
            return correct_answer_str

        try:
            candidate = int(correct_answer_str)
            while str(candidate) in options:
                candidate += 1
            return str(candidate)
        except (TypeError, ValueError):
            candidate = 0
            while str(candidate) in options:
                candidate += 1
            return str(candidate)

