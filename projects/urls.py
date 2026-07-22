from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("", views.project_list, name="list"),
    path("neu/", views.project_create, name="create"),
    path("<uuid:project_id>/", views.project_editor, name="editor"),
    path("<uuid:project_id>/speichern/", views.project_autosave, name="autosave"),
    path("<uuid:project_id>/duplizieren/", views.project_duplicate, name="duplicate"),
    path("<uuid:project_id>/loeschen/", views.project_delete, name="delete"),
    path("<uuid:project_id>/sprecher/neu/", views.speaker_add, name="speaker_add"),
    path("<uuid:project_id>/sprecher/<uuid:speaker_id>/speichern/", views.speaker_autosave, name="speaker_autosave"),
    path("<uuid:project_id>/sprecher/<uuid:speaker_id>/loeschen/", views.speaker_delete, name="speaker_delete"),
    path("<uuid:project_id>/beitraege/neu/", views.segment_add, name="segment_add"),
    path("<uuid:project_id>/beitraege/<uuid:segment_id>/speichern/", views.segment_autosave, name="segment_autosave"),
    path("<uuid:project_id>/beitraege/<uuid:segment_id>/duplizieren/", views.segment_duplicate, name="segment_duplicate"),
    path("<uuid:project_id>/beitraege/<uuid:segment_id>/loeschen/", views.segment_delete, name="segment_delete"),
    path("<uuid:project_id>/beitraege/<uuid:segment_id>/<str:direction>/", views.segment_move, name="segment_move"),
]
