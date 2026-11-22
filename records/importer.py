"""実験結果 YAML (result.yaml) の読み込み・検証・保存。

Copilot等に指示して実験コードから出力させた result.yaml を取り込むためのモジュール。
形式の仕様は docs/result_yaml.md を参照。

検証ルール:
- experiment.code / title / date は必須
- stage / class_type / correction は定義済みの値のみ
- 精度は 0〜100 の数値か、未記録(null)のみ
- 補正は「なし / component のみ / component + calibrated」の3値のみ。
  calibrated stacking 単独は存在しない。component_calibrated の行の zsl は
  「component fusion を適用したZSL（calibrated stacking はZSLに適用されない）」を表す。
"""
import datetime

import yaml

from .models import Experiment, MetricResult

STAGES = {c[0] for c in MetricResult.Stage.choices}
CLASS_TYPES = {c[0] for c in MetricResult.ClassType.choices}
CORRECTIONS = {c[0] for c in MetricResult.Correction.choices}


class ImportError_(Exception):
    """検証エラー。メッセージはそのまま画面に出せる日本語にする。"""


def _require(cond, msg):
    if not cond:
        raise ImportError_(msg)


def _check_accuracy(value, label):
    if value is None:
        return None
    _require(isinstance(value, (int, float)) and not isinstance(value, bool),
             f"{label} は数値で指定してください（値: {value!r}）")
    _require(0 <= float(value) <= 100,
             f"{label} は 0〜100 の範囲で指定してください（値: {value}）")
    return float(value)


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
            "tags": exp.get("tags", "") or "",
        },
        "conditions": data.get("conditions", {}) or {},
        "params": data.get("params", {}) or {},
        "results": [],
    }
    if isinstance(normalized["experiment"]["tags"], list):
        normalized["experiment"]["tags"] = ", ".join(
            str(t) for t in normalized["experiment"]["tags"])
    _require(isinstance(normalized["conditions"], dict),
             "conditions はキー/値のマッピングで指定してください")
    _require(isinstance(normalized["params"], dict),
             "params はキー/値のマッピングで指定してください")

    results = data.get("results", []) or []
    _require(isinstance(results, list), "results はリストで指定してください")
    seen = set()
    for i, r in enumerate(results, start=1):
        label = f"results[{i}]"
        _require(isinstance(r, dict), f"{label} はマッピングで指定してください")
        stage = r.get("stage")
        class_type = r.get("class_type")
        correction = r.get("correction")
        _require(stage in STAGES,
                 f"{label}.stage は {sorted(STAGES)} のいずれかです（値: {stage!r}）")
        _require(class_type in CLASS_TYPES,
                 f"{label}.class_type は {sorted(CLASS_TYPES)} のいずれかです（値: {class_type!r}）")
        _require(correction in CORRECTIONS,
                 f"{label}.correction は {sorted(CORRECTIONS)} のいずれかです（値: {correction!r}）")
        key = (stage, class_type, correction)
        _require(key not in seen,
                 f"{label} の組み合わせ (stage, class_type, correction) が重複しています: {key}")
        seen.add(key)
        gzsl = _check_accuracy(r.get("gzsl"), f"{label}.gzsl")
        zsl = _check_accuracy(r.get("zsl"), f"{label}.zsl")
        _require(gzsl is not None or zsl is not None,
                 f"{label} は gzsl / zsl の少なくとも一方を指定してください")
        normalized["results"].append({
            "stage": stage, "class_type": class_type, "correction": correction,
            "gzsl": gzsl, "zsl": zsl, "note": str(r.get("note", "") or ""),
        })
    return normalized


def save_result(data):
    """正規化済みデータを保存する。同codeの実験があれば更新し、指標は入れ替える。"""
    exp_data = data["experiment"]
    experiment, _created = Experiment.objects.update_or_create(
        code=exp_data["code"],
        defaults={**exp_data,
                  "conditions": data["conditions"],
                  "params": data["params"]},
    )
    experiment.metrics.all().delete()
    MetricResult.objects.bulk_create([
        MetricResult(experiment=experiment, **r) for r in data["results"]
    ])
    return experiment
