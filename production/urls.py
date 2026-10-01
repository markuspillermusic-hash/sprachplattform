from django.urls import path
from . import views

app_name = "production"
urlpatterns = [
    path("neu/", views.create, name="create"),
    path("<uuid:project_id>/", views.detail, name="detail"),
    path("<uuid:project_id>/aktion/", views.action, name="action"),
    path("<uuid:project_id>/status/", views.status, name="status"),
]
