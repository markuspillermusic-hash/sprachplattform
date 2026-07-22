from django.urls import path

from .views import AccountLoginView, AccountLogoutView, FirstPasswordChangeView

app_name = "accounts"

urlpatterns = [
    path("anmelden/", AccountLoginView.as_view(), name="login"),
    path("abmelden/", AccountLogoutView.as_view(), name="logout"),
    path("passwort-aendern/", FirstPasswordChangeView.as_view(), name="password_change"),
]
