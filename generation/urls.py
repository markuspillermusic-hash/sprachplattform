from django.urls import path

from . import views

app_name = "generation"

urlpatterns = [
    path("projekte/<uuid:project_id>/erzeugen/", views.start_generation, name="start"),
    path("auftraege/<uuid:job_id>/status/", views.job_status, name="status"),
    path("auftraege/<uuid:job_id>/erneut/", views.retry_generation, name="retry"),
    path("dateien/<uuid:asset_id>/download/", views.download_audio, name="download"),
    path("dateien/<uuid:asset_id>/anhoeren/", views.play_audio, name="play"),
]
