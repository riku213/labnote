from django.test import TestCase

from .importer import ImportError_, parse_result_yaml, save_result
from .models import Experiment

VALID = """
experiment:
  code: "999999"
  title: "テスト実験"
  date: 2026-01-01
results:
  - stage: pretrain_casia
    class_type: unknown
    correction: component_calibrated
    gzsl: 58.08
    zsl: 62.11
"""


class ImporterTest(TestCase):
    def test_parse_and_save(self):
        data = parse_result_yaml(VALID)
        exp = save_result(data)
        self.assertEqual(exp.code, "999999")
        self.assertEqual(exp.metrics.count(), 1)
        m = exp.metrics.first()
        self.assertEqual(m.gzsl, 58.08)
        self.assertEqual(m.zsl, 62.11)

    def test_save_updates_existing(self):
        save_result(parse_result_yaml(VALID))
        save_result(parse_result_yaml(VALID))
        self.assertEqual(Experiment.objects.filter(code="999999").count(), 1)

    def test_bad_stage_rejected(self):
        bad = VALID.replace("pretrain_casia", "unknown_stage")
        with self.assertRaises(ImportError_):
            parse_result_yaml(bad)

    def test_calibrated_only_correction_does_not_exist(self):
        bad = VALID.replace("component_calibrated", "calibrated")
        with self.assertRaises(ImportError_):
            parse_result_yaml(bad)

    def test_out_of_range_rejected(self):
        bad = VALID.replace("58.08", "158.08")
        with self.assertRaises(ImportError_):
            parse_result_yaml(bad)

    def test_duplicate_combination_rejected(self):
        dup = VALID + """  - stage: pretrain_casia
    class_type: unknown
    correction: component_calibrated
    gzsl: 1.0
"""
        with self.assertRaises(ImportError_):
            parse_result_yaml(dup)
