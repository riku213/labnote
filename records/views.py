import datetime

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from . import biblio
from .forms import (AttachmentForm, ExperimentForm, ImportForm,
                    MetricDefinitionForm, NoteForm, ReadingForm)
from .importer import ImportError_, parse_result_yaml, save_result
from .models import (Attachment, Experiment, MetricDefinition, Note, Reading)


def home(request):
    context = {
        "experiments": Experiment.objects.all()[:10],
        "notes": Note.objects.all()[:5],
        "readings": Reading.objects.all()[:5],
    }
    return render(request, "records/home.html", context)


# ---- 実験 ----

def experiment_list(request):
    experiments = Experiment.objects.prefetch_related("values").all()
    return render(request, "records/experiment_list.html",
                  {"experiments": experiments})


def _grouped_values(experiment):
    """詳細画面用: グループ名 -> 値リスト。各値にグラフ表示用のバー幅(%)を持たせる。

    単位が % の項目は 0-100 を尺度にし、それ以外はグループ内の最大値を尺度にする。
    """
    groups = {}
    for v in experiment.values.select_related("definition").all():
        groups.setdefault(v.definition.group or "その他", []).append(v)
    for values in groups.values():
        group_max = max((v.value for v in values), default=0)
        for v in values:
            if v.definition.unit == "%" and 0 <= v.value <= 100:
                v.bar_width = v.value
            elif group_max > 0 and v.value >= 0:
                v.bar_width = v.value / group_max * 100
            else:
                v.bar_width = None
    return groups


def experiment_detail(request, pk):
    experiment = get_object_or_404(
        Experiment.objects.prefetch_related("attachments", "notes"), pk=pk)
    if request.method == "POST":
        form = AttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            att = form.save(commit=False)
            att.experiment = experiment
            att.save()
            messages.success(request, "画像を添付しました")
            return redirect("records:experiment_detail", pk=pk)
    else:
        form = AttachmentForm()
    context = {
        "experiment": experiment,
        "grouped_values": _grouped_values(experiment),
        "attachment_form": form,
    }
    return render(request, "records/experiment_detail.html", context)


def experiment_create(request):
    form = ExperimentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        exp = form.save()
        return redirect("records:experiment_detail", pk=exp.pk)
    return render(request, "records/form.html",
                  {"form": form, "heading": "実験を手入力で登録"})


def experiment_compare(request):
    """複数実験の評価値を横並びで比較する。行は評価項目の定義から作る（可変）。"""
    selected_ids = request.GET.getlist("ids")
    experiments = Experiment.objects.prefetch_related("values").all()
    selected = [e for e in experiments if str(e.pk) in selected_ids]
    rows = []
    if selected:
        lookup = {}
        definitions = {}
        for e in selected:
            for v in e.values.select_related("definition").all():
                lookup[(e.pk, v.definition_id)] = v.value
                definitions[v.definition_id] = v.definition
        ordered = sorted(definitions.values(),
                         key=lambda d: (d.group, d.sort_order, d.key))
        palette = ["#0017c1", "#d55e00", "#009e73", "#cc79a7", "#56b4e9", "#b26a00"]
        for d in ordered:
            values = [lookup.get((e.pk, d.pk)) for e in selected]
            if any(v is not None for v in values):
                present = [v for v in values if v is not None]
                if d.unit == "%" and all(0 <= v <= 100 for v in present):
                    scale = 100.0
                else:
                    scale = max(present) if present else 0
                bars = []
                for i, (e, v) in enumerate(zip(selected, values)):
                    if v is None:
                        continue
                    width = (v / scale * 100) if scale and v >= 0 else 0
                    bars.append({"code": e.code, "value": v, "width": width,
                                 "color": palette[i % len(palette)]})
                rows.append({
                    "definition": d, "values": values,
                    "best": max(present, default=None), "bars": bars,
                })
    return render(request, "records/experiment_compare.html", {
        "experiments": experiments, "selected": selected, "rows": rows})


def attachment_delete(request, pk):
    """添付画像の削除。確認画面をはさむ。"""
    attachment = get_object_or_404(Attachment, pk=pk)
    back = "records:home"
    back_pk = None
    if attachment.experiment_id:
        back, back_pk = "records:experiment_detail", attachment.experiment_id
    if request.method == "POST":
        attachment.image.delete(save=False)
        attachment.delete()
        messages.success(request, "添付画像を削除しました")
        if back_pk:
            return redirect(back, pk=back_pk)
        return redirect(back)
    return render(request, "records/attachment_confirm_delete.html",
                  {"attachment": attachment})


# ---- 評価項目の定義 ----

def definition_list(request):
    definitions = MetricDefinition.objects.all()
    form = MetricDefinitionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "評価項目を追加しました")
        return redirect("records:definition_list")
    return render(request, "records/definition_list.html",
                  {"definitions": definitions, "form": form})


def definition_edit(request, pk):
    definition = get_object_or_404(MetricDefinition, pk=pk)
    form = MetricDefinitionForm(request.POST or None, instance=definition)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "評価項目を更新しました")
        return redirect("records:definition_list")
    return render(request, "records/form.html",
                  {"form": form, "heading": f"評価項目を編集: {definition.key}"})


# ---- YAML取り込み ----

def import_yaml(request):
    if request.method == "POST":
        form = ImportForm(request.POST, request.FILES)
        if form.is_valid():
            raw = form.cleaned_data["file"].read()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                messages.error(request, "ファイルは UTF-8 で保存してください")
                return redirect("records:import_yaml")
            try:
                data = parse_result_yaml(text)
            except ImportError_ as e:
                messages.error(request, f"取り込めませんでした: {e}")
                return redirect("records:import_yaml")
            request.session["pending_import"] = _serialize_import(data)
            return render(request, "records/import_preview.html", {"data": data})
    else:
        form = ImportForm()
    return render(request, "records/import_upload.html", {"form": form})


def _serialize_import(data):
    d = dict(data)
    exp = dict(d["experiment"])
    exp["date"] = exp["date"].isoformat()
    d["experiment"] = exp
    return d


def _deserialize_import(d):
    d = dict(d)
    exp = dict(d["experiment"])
    exp["date"] = datetime.date.fromisoformat(exp["date"])
    d["experiment"] = exp
    return d


def import_confirm(request):
    if request.method != "POST":
        return redirect("records:import_yaml")
    pending = request.session.pop("pending_import", None)
    if not pending:
        messages.error(request, "取り込み待ちのデータがありません。もう一度アップロードしてください")
        return redirect("records:import_yaml")
    experiment = save_result(_deserialize_import(pending))
    messages.success(request, f"実験 {experiment.code} を取り込みました")
    return redirect("records:experiment_detail", pk=experiment.pk)


# ---- ノート ----

def note_list(request):
    kind = request.GET.get("kind", "")
    notes = Note.objects.all()
    if kind:
        notes = notes.filter(kind=kind)
    return render(request, "records/note_list.html",
                  {"notes": notes, "kind": kind, "kinds": Note.Kind.choices})


def note_create(request):
    form = NoteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("records:note_list")
    return render(request, "records/form.html",
                  {"form": form, "heading": "ノートを書く"})


# ---- 読書記録 ----

SORTS = {
    "-read_date": "読んだ日（新しい順）",
    "read_date": "読んだ日（古い順）",
    "-created_at": "登録日（新しい順）",
    "-rating": "評価（高い順）",
    "title": "タイトル順",
}


def reading_list(request):
    readings = Reading.objects.all()
    item_type = request.GET.get("type", "")
    if item_type in ("paper", "book"):
        readings = readings.filter(item_type=item_type)
    sort = request.GET.get("sort", "-read_date")
    if sort not in SORTS:
        sort = "-read_date"
    readings = readings.order_by(sort, "-id")
    return render(request, "records/reading_list.html", {
        "readings": readings, "item_type": item_type,
        "sort": sort, "sorts": SORTS})


def reading_edit(request, pk):
    reading = get_object_or_404(Reading, pk=pk)
    form = ReadingForm(request.POST or None, instance=reading)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "読書記録を更新しました")
        return redirect("records:reading_list")
    return render(request, "records/reading_form.html",
                  {"form": form, "editing": reading})


def reading_stats(request):
    """読書ダッシュボード: 件数・月別推移・評価の平均などをまとめる。"""
    import datetime as _dt
    from django.db.models import Avg, Count
    readings = Reading.objects.all()
    total = readings.count()
    papers = readings.filter(item_type="paper").count()
    books = readings.filter(item_type="book").count()
    avg_rating = readings.exclude(rating__isnull=True).aggregate(a=Avg("rating"))["a"]
    today = _dt.date.today()
    monthly = []
    max_count = 0
    for i in range(11, -1, -1):
        year = today.year + (today.month - 1 - i) // 12
        month = (today.month - 1 - i) % 12 + 1
        count = readings.filter(read_date__year=year, read_date__month=month).count()
        monthly.append({"label": f"{year}年{month}月", "count": count})
        max_count = max(max_count, count)
    for m in monthly:
        m["width"] = (m["count"] / max_count * 100) if max_count else 0
    by_year = (readings.exclude(read_date__isnull=True)
               .values("read_date__year").annotate(c=Count("id"))
               .order_by("-read_date__year"))
    return render(request, "records/reading_stats.html", {
        "total": total, "papers": papers, "books": books,
        "avg_rating": avg_rating, "monthly": monthly, "by_year": by_year,
        "this_year": readings.filter(read_date__year=today.year).count(),
        "this_month": readings.filter(
            read_date__year=today.year, read_date__month=today.month).count(),
    })


def reading_search(request):
    """タイトルで論文・本を検索し、候補から選べる画面。"""
    item_type = request.GET.get("type", "paper")
    query = request.GET.get("q", "").strip()
    results = []
    if query:
        if item_type == "book":
            results = biblio.search_books(query)
        else:
            results = biblio.search_papers(query)
        if not results:
            messages.warning(request, "候補が見つかりませんでした。キーワードを変えるか、手入力してください")
    return render(request, "records/reading_search.html", {
        "item_type": item_type, "query": query, "results": results})


def reading_create(request):
    initial = {}
    # 検索結果やDOI/ISBN検索からの引き継ぎ（GETパラメータ）
    for field in ("item_type", "title", "authors", "year", "venue",
                  "doi", "isbn", "url", "cover_url"):
        value = request.GET.get(field, "")
        if value:
            initial[field] = value
    doi = request.GET.get("doi_lookup", "").strip()
    isbn = request.GET.get("isbn_lookup", "").strip()
    if doi:
        found = biblio.lookup_doi(doi)
        if found:
            initial = {**found, "item_type": "paper"}
            messages.success(request, "Crossrefから書誌情報を取得しました")
        else:
            messages.warning(request, "DOIから書誌情報を取得できませんでした。手入力してください")
    elif isbn:
        found = biblio.lookup_isbn(isbn)
        if found:
            initial = {**found, "item_type": "book"}
            messages.success(request, "openBD / Google Booksから書誌情報を取得しました")
        else:
            messages.warning(request, "ISBNから書誌情報を取得できませんでした。手入力してください")
    form = ReadingForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("records:reading_list")
    return render(request, "records/reading_form.html", {"form": form})
