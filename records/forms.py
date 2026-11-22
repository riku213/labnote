from django import forms

from .models import Attachment, Experiment, MetricDefinition, Note, Reading


class ExperimentForm(forms.ModelForm):
    class Meta:
        model = Experiment
        fields = ["code", "title", "date", "background", "changes", "discussion",
                  "memo", "git_commit", "checkpoint", "tags"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ["kind", "title", "date", "body", "experiment", "tags"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}


class ReadingForm(forms.ModelForm):
    class Meta:
        model = Reading
        fields = ["item_type", "title", "authors", "year", "venue", "doi", "isbn",
                  "url", "cover_url", "read_date", "rating", "summary", "impression", "tags"]
        widgets = {"read_date": forms.DateInput(attrs={"type": "date"})}


class AttachmentForm(forms.ModelForm):
    class Meta:
        model = Attachment
        fields = ["image", "caption"]


class ImportForm(forms.Form):
    file = forms.FileField(label="result.yaml ファイル")


class MetricDefinitionForm(forms.ModelForm):
    class Meta:
        model = MetricDefinition
        fields = ["key", "label", "group", "unit", "sort_order", "is_active"]
