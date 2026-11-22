from django.core.management.base import BaseCommand

from records.export import export_all


class Command(BaseCommand):
    help = "記録を人間が読めるMarkdown一式に書き出す（Google Driveへはこの結果をアップロードする）"

    def add_arguments(self, parser):
        parser.add_argument("--out", default="export",
                            help="書き出し先ディレクトリ（既定: export/）")

    def handle(self, *args, **options):
        count = export_all(options["out"])
        self.stdout.write(self.style.SUCCESS(
            f"{count} ファイルを {options['out']} に書き出しました"))
