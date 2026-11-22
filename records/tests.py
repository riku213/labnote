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
