from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("konto/", include("accounts.urls")),
    path("projekte/", include("projects.urls")),
    path("audio/", include("generation.urls")),
    path("", include("core.urls")),
]
