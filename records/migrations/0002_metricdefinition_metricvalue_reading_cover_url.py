# 評価項目を固定列（MetricResult）から可変の定義＋値（MetricDefinition/MetricValue）へ移行する。
# 既存の MetricResult の値は、キーを組み立てて MetricValue に移す。
from django.db import migrations, models
import django.db.models.deletion

STAGE_LABEL = {"pretrain_casia": "事前学習 (CASIA)", "finetune_kuzushiji": "ファインチューニング (くずし字)"}
CLASS_LABEL = {"known": "既知クラス", "unknown": "未知クラス"}
CORR_LABEL = {"none": "補正なし", "component": "component fusion のみ",
              "component_calibrated": "component fusion + calibrated stacking"}


def forwards(apps, schema_editor):
    MetricResult = apps.get_model("records", "MetricResult")
    MetricDefinition = apps.get_model("records", "MetricDefinition")
    MetricValue = apps.get_model("records", "MetricValue")
    defs = {}
    order = 0
    for m in MetricResult.objects.all().order_by("id"):
        for kind in ("gzsl", "zsl"):
            value = getattr(m, kind)
            if value is None:
                continue
            key = f"{m.stage}.{m.class_type}.{m.correction}.{kind}"
            if key not in defs:
                order += 10
                defs[key], _ = MetricDefinition.objects.get_or_create(
                    key=key,
                    defaults={
                        "label": f"{CLASS_LABEL.get(m.class_type, m.class_type)} / "
                                 f"{CORR_LABEL.get(m.correction, m.correction)} / {kind.upper()}",
                        "group": STAGE_LABEL.get(m.stage, m.stage),
                        "unit": "%",
                        "sort_order": order,
                    })
            MetricValue.objects.update_or_create(
                experiment_id=m.experiment_id, definition=defs[key],
                defaults={"value": value, "note": m.note})


class Migration(migrations.Migration):
    dependencies = [("records", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="MetricDefinition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(help_text="例: pretrain_casia.unknown.component_calibrated.gzsl / val_loss など", max_length=200, unique=True, verbose_name="キー")),
                ("label", models.CharField(blank=True, help_text="空ならキーそのまま表示", max_length=300, verbose_name="表示名")),
                ("group", models.CharField(blank=True, help_text="例: 事前学習 (CASIA)", max_length=100, verbose_name="表示グループ")),
                ("unit", models.CharField(blank=True, default="%", max_length=16, verbose_name="単位")),
                ("sort_order", models.IntegerField(default=0, verbose_name="並び順")),
                ("is_active", models.BooleanField(default=True, verbose_name="有効")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"verbose_name": "評価項目の定義", "verbose_name_plural": "評価項目の定義",
                     "ordering": ["group", "sort_order", "key"]},
        ),
        migrations.CreateModel(
            name="MetricValue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("value", models.FloatField(verbose_name="値")),
                ("note", models.CharField(blank=True, max_length=200, verbose_name="注記")),
                ("definition", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="values", to="records.metricdefinition", verbose_name="評価項目")),
                ("experiment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="values", to="records.experiment", verbose_name="実験")),
            ],
            options={"verbose_name": "評価値", "verbose_name_plural": "評価値",
                     "ordering": ["definition__group", "definition__sort_order", "definition__key"],
                     "unique_together": {("experiment", "definition")}},
        ),
        migrations.AddField(
            model_name="reading",
            name="cover_url",
            field=models.URLField(blank=True, verbose_name="表紙画像URL"),
        ),
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.DeleteModel(name="MetricResult"),
    ]
