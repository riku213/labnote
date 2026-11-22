from django.urls import path

from . import views

app_name = 'records'

urlpatterns = [
    path('', views.home, name='home'),
    path('experiments/', views.experiment_list, name='experiment_list'),
    path('experiments/new/', views.experiment_create, name='experiment_create'),
    path('experiments/compare/', views.experiment_compare, name='experiment_compare'),
    path('experiments/<int:pk>/', views.experiment_detail, name='experiment_detail'),
    path('attachments/<int:pk>/delete/', views.attachment_delete, name='attachment_delete'),
    path('definitions/', views.definition_list, name='definition_list'),
    path('definitions/<int:pk>/edit/', views.definition_edit, name='definition_edit'),
    path('import/', views.import_yaml, name='import_yaml'),
    path('import/confirm/', views.import_confirm, name='import_confirm'),
    path('notes/', views.note_list, name='note_list'),
    path('notes/new/', views.note_create, name='note_create'),
    path('readings/', views.reading_list, name='reading_list'),
    path('readings/search/', views.reading_search, name='reading_search'),
    path('readings/new/', views.reading_create, name='reading_create'),
]
