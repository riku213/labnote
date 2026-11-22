"""記録を人間が読める Markdown に書き出す。

Google Drive へは、この書き出し結果（Markdown + 画像ファイル）を
フォルダごとアップロードする想定。正本はDB、Drive側は「読むための写し」。
"""
import shutil
from pathlib import Path

from .models import Experiment, MetricResult, Note, Reading

STAGE_ORDER = [c[0] for c in MetricResult.Stage.choices]
STAGE_LABEL = dict(MetricResult.Stage.choices)
CLASS_LABEL = dict(MetricResult.ClassType.choices)
CORR_LABEL = dict(MetricResult.Correction.choices)
CORR_ORDER = [c[0] for c in MetricResult.Correction.choices]


def _fmt(v):
    return "" if v is None else f"{v:g}"


def metric_table_md(experiment):
    lines = []
    by_stage = {}
    for m in experiment.metrics.all():
        by_stage.setdefault(m.stage, {})[(m.class_type, m.correction)] = m
    for stage in STAGE_ORDER:
        if stage not in by_stage:
            continue
        lines.append(f"### {STAGE_LABEL[stage]}")
        lines.append("")
        header = "| クラス | " + " | ".join(
            f"{CORR_LABEL[c]} GZSL | {CORR_LABEL[c]} ZSL" for c in CORR_ORDER) + " |"
        lines.append(header)
        lines.append("|" + "---|" * (1 + 2 * len(CORR_ORDER)))
        for class_type, class_label in MetricResult.ClassType.choices:
            cells = []
            for corr in CORR_ORDER:
                m = by_stage[stage].get((class_type, corr))
                cells.append(_fmt(m.gzsl) if m else "")
                cells.append(_fmt(m.zsl) if m else "")
            lines.append(f"| {class_label} | " + " | ".join(cells) + " |")
        lines.append("")
    lines.append("※ ZSL に calibrated stacking は適用されません。"
                 "「component fusion + calibrated stacking」列の ZSL は component fusion のみの値です。")
    lines.append("")
    return "\n".join(lines)


def experiment_md(experiment, asset_prefix=""):
    parts = [f"# {experiment.code} {experiment.title}", "",
             f"- 日付: {experiment.date}"]
    if experiment.git_commit:
        parts.append(f"- 実験コードのコミット: {experiment.git_commit}")
    if experiment.checkpoint:
        parts.append(f"- チェックポイント: {experiment.checkpoint}")
    if experiment.tags:
        parts.append(f"- タグ: {experiment.tags}")
    parts.append("")
    parts.append("## 精度")
    parts.append("")
    parts.append(metric_table_md(experiment))
    if experiment.conditions:
        parts.append("## 実験条件")
        parts.append("")
        for k, v in experiment.conditions.items():
            parts.append(f"- {k}: {v}")
        parts.append("")
    if experiment.params:
        parts.append("## 学習パラメータ")
        parts.append("")
        for k, v in experiment.params.items():
            parts.append(f"- {k}: {v}")
        parts.append("")
    for heading, text in (("背景・問題意識", experiment.background),
                          ("変更点", experiment.changes),
                          ("結果の考察", experiment.discussion),
                          ("メモ", experiment.memo)):
        if text:
            parts += [f"## {heading}", "", text, ""]
    atts = list(experiment.attachments.all())
    if atts:
        parts.append("## 添付画像")
        parts.append("")
        for a in atts:
            name = Path(a.image.name).name
            parts.append(f"![{a.caption}]({asset_prefix}assets/{name})")
            if a.caption:
                parts.append(a.caption)
            parts.append("")
    return "\n".join(parts)


def note_md(note):
    parts = [f"# {note.title}", "",
             f"- 日付: {note.date}",
             f"- 種類: {note.get_kind_display()}"]
    if note.experiment:
        parts.append(f"- 関連する実験: {note.experiment.code} {note.experiment.title}")
    if note.tags:
        parts.append(f"- タグ: {note.tags}")
    parts += ["", note.body, ""]
    return "\n".join(parts)


def readings_md(readings):
    parts = ["# 読書記録（論文・本）", ""]
    for r in readings:
        parts.append(f"## [{r.get_item_type_display()}] {r.title}")
        meta = []
        if r.authors:
            meta.append(r.authors)
        if r.year:
            meta.append(str(r.year))
        if r.venue:
            meta.append(r.venue)
        if r.doi:
            meta.append(f"DOI: {r.doi}")
        if r.isbn:
            meta.append(f"ISBN: {r.isbn}")
        if r.read_date:
            meta.append(f"読んだ日: {r.read_date}")
        if r.rating:
            meta.append(f"評価: {r.rating}/5")
        if meta:
            parts.append(" / ".join(meta))
        parts.append("")
        if r.summary:
            parts += ["### 要約", "", r.summary, ""]
        if r.impression:
            parts += ["### 感想・メモ", "", r.impression, ""]
    return "\n".join(parts)


def export_all(out_dir):
    """out_dir 以下に Markdown 一式と画像を書き出す。作成したファイル数を返す。"""
    out = Path(out_dir)
    (out / "experiments").mkdir(parents=True, exist_ok=True)
    (out / "notes").mkdir(parents=True, exist_ok=True)
    (out / "assets").mkdir(parents=True, exist_ok=True)
    count = 0

    experiments = list(Experiment.objects.prefetch_related("metrics", "attachments"))
    index = ["# labnote 書き出し", "", "## 実験一覧", "",
             "| 日付 | ID | タイトル |", "|---|---|---|"]
    for e in experiments:
        fname = f"experiments/{e.code}.md"
        index.append(f"| {e.date} | {e.code} | [{e.title}]({fname}) |")
        (out / fname).write_text(experiment_md(e, asset_prefix="../"), encoding="utf-8")
        count += 1
        for a in e.attachments.all():
            src = Path(a.image.path)
            if src.exists():
                shutil.copyfile(src, out / "assets" / src.name)
                count += 1
    (out / "index.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    count += 1

    for n in Note.objects.all():
        fname = f"notes/{n.date}_{n.pk}.md"
        (out / fname).write_text(note_md(n), encoding="utf-8")
        count += 1

    readings = list(Reading.objects.all())
    if readings:
        (out / "readings.md").write_text(readings_md(readings), encoding="utf-8")
        count += 1
    return count
