from django.test import TestCase

from .importer import ImportError_, parse_result_yaml, save_result
from .models import Experiment, MetricDefinition

LEGACY = """
experiment:
  code: "999999"
  title: "テスト実験（v1形式）"
  date: 2026-01-01
results:
  - stage: pretrain_casia
    class_type: unknown
    correction: component_calibrated
    gzsl: 58.08
    zsl: 62.11
"""

V2 = """
experiment:
  code: "999998"
  title: "テスト実験（v2形式）"
  date: 2026-01-02
metrics:
  - key: val_loss
    value: 0.25
    label: "検証ロス"
    group: "学習"
    unit: ""
  - key: custom.accuracy.top5
    value: 88.5
"""


class ImporterTest(TestCase):
    def test_legacy_parse_and_save(self):
        exp = save_result(parse_result_yaml(LEGACY))
        self.assertEqual(exp.values.count(), 2)
        keys = set(exp.values.values_list("definition__key", flat=True))
        self.assertIn("pretrain_casia.unknown.component_calibrated.gzsl", keys)
        self.assertIn("pretrain_casia.unknown.component_calibrated.zsl", keys)

    def test_v2_free_key(self):
        exp = save_result(parse_result_yaml(V2))
        self.assertEqual(exp.values.count(), 2)
        d = MetricDefinition.objects.get(key="val_loss")
        self.assertEqual(d.label, "検証ロス")
        self.assertEqual(d.group, "学習")

    def test_save_updates_existing(self):
        save_result(parse_result_yaml(LEGACY))
        save_result(parse_result_yaml(LEGACY))
        self.assertEqual(Experiment.objects.filter(code="999999").count(), 1)
        self.assertEqual(Experiment.objects.get(code="999999").values.count(), 2)

    def test_bad_stage_rejected(self):
        bad = LEGACY.replace("pretrain_casia", "unknown_stage")
        with self.assertRaises(ImportError_):
            parse_result_yaml(bad)

    def test_calibrated_only_correction_does_not_exist(self):
        bad = LEGACY.replace("component_calibrated", "calibrated")
        with self.assertRaises(ImportError_):
            parse_result_yaml(bad)

    def test_out_of_range_rejected(self):
        bad = LEGACY.replace("58.08", "158.08")
        with self.assertRaises(ImportError_):
            parse_result_yaml(bad)

    def test_duplicate_combination_rejected(self):
        dup = LEGACY + """  - stage: pretrain_casia
    class_type: unknown
    correction: component_calibrated
    gzsl: 1.0
"""
        with self.assertRaises(ImportError_):
            parse_result_yaml(dup)

    def test_bad_key_rejected(self):
        bad = V2.replace("val_loss", "bad key!")
        with self.assertRaises(ImportError_):
            parse_result_yaml(bad)


class AttachmentDeleteTest(TestCase):
    def test_delete_requires_post_and_removes(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import Attachment
        exp = save_result(parse_result_yaml(V2))
        att = Attachment.objects.create(
            experiment=exp,
            image=SimpleUploadedFile("x.png", b"\x89PNG", content_type="image/png"))
        resp = self.client.get(f"/attachments/{att.pk}/delete/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Attachment.objects.filter(pk=att.pk).exists())
        resp = self.client.post(f"/attachments/{att.pk}/delete/")
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Attachment.objects.filter(pk=att.pk).exists())


class ReadingFeatureTest(TestCase):
    def setUp(self):
        import datetime
        from .models import Reading
        self.book = Reading.objects.create(
            item_type="book", title="テストの本", authors="著者",
            read_date=datetime.date(2026, 11, 1), rating=4, impression="よかった")
        self.paper = Reading.objects.create(
            item_type="paper", title="Test Paper", authors="A",
            read_date=datetime.date(2026, 10, 1), rating=5)

    def test_filter_by_type(self):
        resp = self.client.get("/readings/?type=book")
        self.assertContains(resp, "テストの本")
        self.assertNotContains(resp, "Test Paper")

    def test_edit_impression(self):
        resp = self.client.post(f"/readings/{self.book.pk}/edit/", {
            "item_type": "book", "title": "テストの本", "authors": "著者",
            "read_date": "2026-11-01", "rating": 4, "impression": "書き直した感想"})
        self.assertEqual(resp.status_code, 302)
        self.book.refresh_from_db()
        self.assertEqual(self.book.impression, "書き直した感想")

    def test_stats(self):
        resp = self.client.get("/readings/stats/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "2 件")


class ReadingImageTest(TestCase):
    def test_attach_paste_flow_and_thumbnail(self):
        import datetime
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import Reading
        r = Reading.objects.create(item_type="paper", title="画像つき論文",
                                   read_date=datetime.date(2026, 11, 20))
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (8, 8), (255, 0, 0)).save(buf, format="PNG")
        png = SimpleUploadedFile("shot.png", buf.getvalue(), content_type="image/png")
        resp = self.client.post(f"/readings/{r.pk}/", {"image": png, "caption": "図1"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(r.attachments.count(), 1)
        resp = self.client.get("/readings/")
        self.assertContains(resp, "画像つき論文")
        resp = self.client.get(f"/readings/{r.pk}/")
        self.assertContains(resp, "図1")


class ThemeTest(TestCase):
    def test_default_theme_is_standard(self):
        resp = self.client.get("/")
        self.assertContains(resp, 'data-theme="standard"')

    def test_theme_switch_via_settings(self):
        resp = self.client.post("/settings/", {"theme": "material"})
        self.assertEqual(resp.status_code, 302)
        resp = self.client.get("/")
        self.assertContains(resp, 'data-theme="material"')
        resp = self.client.post("/settings/", {"theme": "apple"})
        resp = self.client.get("/")
        self.assertContains(resp, 'data-theme="apple"')

    def test_invalid_theme_falls_back(self):
        self.client.cookies.load({"labnote_theme": "bogus"})
        resp = self.client.get("/")
        self.assertContains(resp, 'data-theme="standard"')


class MoreThemesAndDateTest(TestCase):
    def test_all_themes_apply(self):
        for theme in ("standard", "material", "apple", "github", "dark",
                      "dracula", "solarized", "washi", "terminal", "newspaper"):
            self.client.post("/settings/", {"theme": theme})
            resp = self.client.get("/")
            self.assertContains(resp, f'data-theme="{theme}"')

    def test_date_defaults_to_today(self):
        import datetime
        today = datetime.date.today().isoformat()
        self.assertContains(self.client.get("/experiments/new/"), f'value="{today}"')
        self.assertContains(self.client.get("/readings/new/"), f'value="{today}"')
        self.assertContains(self.client.get("/notes/new/"), f'value="{today}"')
