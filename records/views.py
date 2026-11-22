from django.shortcuts import render

from .models import Experiment, Note, Reading


def home(request):
    context = {
        'experiments': Experiment.objects.all()[:10],
        'notes': Note.objects.all()[:5],
        'readings': Reading.objects.all()[:5],
    }
    return render(request, 'records/home.html', context)
