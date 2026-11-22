import datetime

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from . import biblio
from .forms import AttachmentForm, ExperimentForm, ImportForm, NoteForm, ReadingForm
from .importer import ImportError_, parse_result_yaml, save_result
from .models import Experiment, MetricResult, Note, Reading


def home(request):
    context = {
        "experiments": Experiment.objects.all()[:10],
        "notes": Note.objects.all()[:5],
        "readings": Reading.objects.all()[:5],
    }
    return render(request, "records/home.html", context)


# ---- 実験 ----

def experiment_list(request):
    experiments = Experiment.objects.prefetch_related("metrics").all()
    return render(request, "records/experiment_list.html",
                  {"experiments": experiments})


def _metric_matrix(experiment):
    """詳細画面用: stage -> class_type -> correction -> MetricResult の辞書。"""
    matrix = {}
    for m in experiment.metrics.all():
        matrix.setdefault(m.stage, {}).setdefault(m.class_type, {})[m.correction] = m
    return matrix


def experiment_detail(request, pk):
    experiment = get_object_or_404(
        Experiment.objects.prefetch_related("metrics", "attachments", "notes"), pk=pk)
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
        "matrix": _metric_matrix(experiment),
        "stages": MetricResult.Stage.choices,
        "class_types": MetricResult.ClassType.choices,
        "corrections": MetricResult.Correction.choices,
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
    """複数実験の指標を横並びで比較する。"""
    selected_ids = request.GET.getlist("ids")
    experiments = Experiment.objects.prefetch_related("metrics").all()
    selected = [e for e in experiments if str(e.pk) in selected_ids]
    rows = []
    if selected:
        keys = []
        for e in selected:
            for m in e.metrics.all():
                key = (m.stage, m.class_type, m.correction)
                if key not in keys:
                    keys.append(key)
        stage_labels = dict(MetricResult.Stage.choices)
        class_labels = dict(MetricResult.ClassType.choices)
        corr_labels = dict(MetricResult.Correction.choices)
        lookup = {}
        for e in selected:
            for m in e.metrics.all():
                lookup[(e.pk, m.stage, m.class_type, m.correction)] = m
        for (stage, class_type, correction) in keys:
            for metric_name in ("gzsl", "zsl"):
                values = []
                for e in selected:
                    m = lookup.get((e.pk, stage, class_type, correction))
                    values.append(getattr(m, metric_name) if m else None)
                if any(v is not None for v in values):
                    rows.append({
                        "label": (f"{stage_labels[stage]} / {class_labels[class_type]} / "
                                  f"{corr_labels[correction]} / {metric_name.upper()}"),
                        "values": values,
                        "best": max((v for v in values if v is not None), default=None),
                    })
    return render(request, "records/experiment_compare.html", {
        "experiments": experiments, "selected": selected, "rows": rows})


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

def reading_list(request):
    readings = Reading.objects.all()
    return render(request, "records/reading_list.html", {"readings": readings})


def reading_create(request):
    initial = {}
    doi = request.GET.get("doi", "").strip()
    isbn = request.GET.get("isbn", "").strip()
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
