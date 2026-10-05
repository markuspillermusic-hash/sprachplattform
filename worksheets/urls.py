from django.urls import path
from . import views

app_name = "worksheets"
urlpatterns = [
    path("projekt/<uuid:project_id>/", views.start, name="start"),
    path("<uuid:worksheet_id>/", views.detail, name="detail"),
    path("<uuid:worksheet_id>/status/", views.status, name="status"),
    path("<uuid:worksheet_id>/vorschau/<str:audience>/", views.preview, name="preview"),
    path("<uuid:worksheet_id>/download/<str:audience>/<str:file_format>/", views.download, name="download"),
]
