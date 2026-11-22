from django import forms

from .models import Attachment, Experiment, Note, Reading


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
                  "url", "read_date", "rating", "summary", "impression", "tags"]
        widgets = {"read_date": forms.DateInput(attrs={"type": "date"})}


class AttachmentForm(forms.ModelForm):
    class Meta:
        model = Attachment
        fields = ["image", "caption"]


class ImportForm(forms.Form):
    file = forms.FileField(label="result.yaml ファイル")
