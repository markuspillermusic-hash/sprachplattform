from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.views import View

from .forms import RateLimitedAuthenticationForm


class AccountLoginView(LoginView):
    authentication_form = RateLimitedAuthenticationForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


class AccountLogoutView(LogoutView):
    http_method_names = ["post"]


class FirstPasswordChangeView(LoginRequiredMixin, View):
    template_name = "accounts/password_change.html"

    def get(self, request):
        return render(request, self.template_name, {"form": PasswordChangeForm(request.user)})

    def post(self, request):
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            user.must_change_password = False
            user.save(update_fields=["must_change_password"])
            update_session_auth_hash(request, user)
            messages.success(request, "Ihr persönliches Passwort wurde gespeichert.")
            return redirect("core:home")
        return render(request, self.template_name, {"form": form}, status=422)

