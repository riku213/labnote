"""実験結果 YAML (result.yaml) の読み込み・検証・保存。

形式は2世代をサポートする:
- v2（推奨）: metrics に「キー = 値」のリストで書く。キーは自由に決められ、
  評価項目は固定ではない。未知のキーは取り込み時に評価項目として自動登録される。
- v1（互換）: results に stage / class_type / correction / gzsl / zsl で書く。
  内部では v2 のキー（例: pretrain_casia.unknown.component_calibrated.gzsl）へ変換する。

仕様は docs/result_yaml.md を参照。
"""
import datetime
import re

import yaml

from .models import Experiment, MetricDefinition, MetricValue

# v1互換用の値域
STAGES = {"pretrain_casia", "finetune_kuzushiji"}
CLASS_TYPES = {"known", "unknown"}
CORRECTIONS = {"none", "component", "component_calibrated"}

KEY_RE = re.compile(r"^[A-Za-z0-9_.\-/]+$")


class ImportError_(Exception):
    """検証エラー。メッセージはそのまま画面に出せる日本語にする。"""


def _require(cond, msg):
    if not cond:
        raise ImportError_(msg)


def _check_number(value, label):
    _require(isinstance(value, (int, float)) and not isinstance(value, bool),
             f"{label} は数値で指定してください（値: {value!r}）")
    return float(value)


def _check_accuracy(value, label):
    if value is None:
        return None
    v = _check_number(value, label)
    _require(0 <= v <= 100, f"{label} は 0〜100 の範囲で指定してください（値: {value}）")
    return v


def _parse_metrics_v2(raw):
    _require(isinstance(raw, list), "metrics はリストで指定してください")
    metrics, seen = [], set()
    for i, r in enumerate(raw, start=1):
        label = f"metrics[{i}]"
        _require(isinstance(r, dict), f"{label} はマッピングで指定してください")
        key = r.get("key") or r.get("name")
        _require(isinstance(key, str) and KEY_RE.match(key),
                 f"{label}.key は英数字と _ . - / で指定してください（値: {key!r}）")
        _require(key not in seen, f"{label} のキー {key} が重複しています")
        seen.add(key)
        _require("value" in r, f"{label}（{key}）には value が必要です")
        metrics.append({
            "key": key,
            "value": _check_number(r["value"], f"{label}.value"),
            "note": str(r.get("note", "") or ""),
            "label": str(r.get("label", "") or ""),
            "group": str(r.get("group", "") or ""),
            "unit": str(r.get("unit", "") or ""),
        })
    return metrics


def _parse_results_v1(raw):
    """v1の results を v2の metrics（キー=値）へ変換する。"""
    _require(isinstance(raw, list), "results はリストで指定してください")
    metrics, seen = [], set()
    for i, r in enumerate(raw, start=1):
        label = f"results[{i}]"
        _require(isinstance(r, dict), f"{label} はマッピングで指定してください")
        stage, class_type, correction = r.get("stage"), r.get("class_type"), r.get("correction")
        _require(stage in STAGES, f"{label}.stage は {sorted(STAGES)} のいずれかです（値: {stage!r}）")
        _require(class_type in CLASS_TYPES,
                 f"{label}.class_type は {sorted(CLASS_TYPES)} のいずれかです（値: {class_type!r}）")
        _require(correction in CORRECTIONS,
                 f"{label}.correction は {sorted(CORRECTIONS)} のいずれかです（値: {correction!r}）")
        gzsl = _check_accuracy(r.get("gzsl"), f"{label}.gzsl")
        zsl = _check_accuracy(r.get("zsl"), f"{label}.zsl")
        _require(gzsl is not None or zsl is not None,
                 f"{label} は gzsl / zsl の少なくとも一方を指定してください")
        for kind, value in (("gzsl", gzsl), ("zsl", zsl)):
            if value is None:
                continue
            key = f"{stage}.{class_type}.{correction}.{kind}"
            _require(key not in seen, f"{label} の組み合わせが重複しています: {key}")
            seen.add(key)
            metrics.append({"key": key, "value": value,
                            "note": str(r.get("note", "") or ""),
                            "label": "", "group": "", "unit": ""})
    return metrics


def parse_result_yaml(text):
    """YAML文字列を検証し、保存可能な dict に正規化する。失敗時は ImportError_。"""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ImportError_(f"YAMLとして読み取れませんでした: {e}")
    _require(isinstance(data, dict), "YAMLのトップレベルはマッピングである必要があります")

    exp = data.get("experiment")
    _require(isinstance(exp, dict), "experiment セクションが必要です")
    for field in ("code", "title", "date"):
        _require(exp.get(field) not in (None, ""), f"experiment.{field} は必須です")
    date = exp["date"]
    if isinstance(date, datetime.datetime):
        date = date.date()
    _require(isinstance(date, datetime.date),
             "experiment.date は日付（例: 2026-11-09）で指定してください")

    tags = exp.get("tags", "") or ""
    if isinstance(tags, list):
        tags = ", ".join(str(t) for t in tags)
    normalized = {
        "experiment": {
            "code": str(exp["code"]),
            "title": str(exp["title"]),
            "date": date,
            "background": exp.get("background", "") or "",
            "changes": exp.get("changes", "") or "",
            "discussion": exp.get("discussion", "") or "",
            "memo": exp.get("memo", "") or "",
            "git_commit": str(exp.get("git_commit", "") or ""),
            "checkpoint": str(exp.get("checkpoint", "") or ""),
            "tags": tags,
        },
        "conditions": data.get("conditions", {}) or {},
        "params": data.get("params", {}) or {},
        "metrics": [],
    }
    _require(isinstance(normalized["conditions"], dict),
             "conditions はキー/値のマッピングで指定してください")
    _require(isinstance(normalized["params"], dict),
             "params はキー/値のマッピングで指定してください")

    if data.get("metrics"):
        normalized["metrics"] += _parse_metrics_v2(data["metrics"])
    if data.get("results"):
        normalized["metrics"] += _parse_results_v1(data["results"])
    keys = [m["key"] for m in normalized["metrics"]]
    _require(len(keys) == len(set(keys)), "metrics と results の間でキーが重複しています")
    return normalized


def get_or_create_definition(m):
    """指標定義を取得する。未知のキーは自動登録する（評価項目は可変という前提）。"""
    defaults = {}
    if m.get("label"):
        defaults["label"] = m["label"]
    if m.get("group"):
        defaults["group"] = m["group"]
    if m.get("unit"):
        defaults["unit"] = m["unit"]
    definition, _ = MetricDefinition.objects.get_or_create(key=m["key"], defaults=defaults)
    return definition


def save_result(data):
    """正規化済みデータを保存する。同codeの実験があれば更新し、評価値は入れ替える。"""
    exp_data = data["experiment"]
    experiment, _created = Experiment.objects.update_or_create(
        code=exp_data["code"],
        defaults={**exp_data,
                  "conditions": data["conditions"],
                  "params": data["params"]},
    )
    experiment.values.all().delete()
    MetricValue.objects.bulk_create([
        MetricValue(experiment=experiment,
                    definition=get_or_create_definition(m),
                    value=m["value"], note=m["note"])
        for m in data["metrics"]
    ])
    return experiment
