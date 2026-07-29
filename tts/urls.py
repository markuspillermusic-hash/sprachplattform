from django.urls import path

from . import views


app_name = "tts"

urlpatterns = [
    path("", views.voice_catalog, name="catalog"),
    path("<int:voice_id>/favorit/", views.favorite_toggle, name="favorite_toggle"),
]
