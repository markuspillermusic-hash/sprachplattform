from django.urls import path

from .views import (
    AccountLoginView,
    AccountLogoutView,
    FirstPasswordChangeView,
    student_access_create,
    student_access_list,
    student_access_reset_password,
    student_access_revoke,
)

app_name = "accounts"

urlpatterns = [
    path("anmelden/", AccountLoginView.as_view(), name="login"),
    path("abmelden/", AccountLogoutView.as_view(), name="logout"),
    path("passwort-aendern/", FirstPasswordChangeView.as_view(), name="password_change"),
    path("schuelerzugaenge/", student_access_list, name="student_access_list"),
    path("schuelerzugaenge/neu/", student_access_create, name="student_access_create"),
    path(
        "schuelerzugaenge/<uuid:access_id>/sperren/",
        student_access_revoke,
        name="student_access_revoke",
    ),
    path(
        "schuelerzugaenge/<uuid:access_id>/passwort-neu/",
        student_access_reset_password,
        name="student_access_reset_password",
    ),
]
