from django.urls import path
from . import views

app_name = "audio_studio"
urlpatterns = [
    path("<uuid:project_id>/", views.editor, name="editor"),
    path("<uuid:project_id>/state/", views.state, name="state"),
    path("<uuid:project_id>/save/", views.save, name="save"),
    path("<uuid:project_id>/upload/", views.upload, name="upload"),
    path("<uuid:project_id>/import/", views.import_speech, name="import"),
    path("<uuid:project_id>/generate/", views.generate, name="generate"),
    path("<uuid:project_id>/export/", views.export, name="export"),
    path("<uuid:project_id>/jobs/", views.jobs, name="jobs"),
    path("<uuid:project_id>/assets/<uuid:asset_id>/", views.asset, name="asset"),
]
