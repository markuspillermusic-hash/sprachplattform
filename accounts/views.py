from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.views import View
from usage_control.models import UsageEvent
from tts.models import TTSConfiguration

from .forms import RateLimitedAuthenticationForm, TemporaryStudentAccessForm
from .models import TemporaryStudentAccess
from .services import (
    create_temporary_student_accesses,
    reset_student_access_password,
    revoke_temporary_student_access,
)


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


def _can_manage_student_accesses(user):
    return bool(
        user.is_authenticated
        and (user.is_staff or user.role in (user.Role.ADMIN, user.Role.TEACHER))
    )


def _manageable_accesses(user):
    queryset = TemporaryStudentAccess.objects.select_related("teacher", "student")
    if user.is_staff or user.role == user.Role.ADMIN:
        return queryset
    return queryset.filter(teacher=user)


def _require_teacher(user):
    if not _can_manage_student_accesses(user):
        raise PermissionDenied


def _usage_by_student(accesses):
    student_ids = [access.student_id for access in accesses]
    rows = (
        UsageEvent.objects.filter(
            user_id__in=student_ids,
            status__in=(UsageEvent.Status.RESERVED, UsageEvent.Status.COMMITTED),
        )
        .values("user_id", "provider")
        .annotate(
            characters=Sum("character_count"),
            requests=Count("id"),
        )
    )
    usage = {}
    for row in rows:
        usage.setdefault(row["user_id"], {})[row["provider"]] = row
    return usage


def _tts_estimated_rate():
    configuration = TTSConfiguration.objects.filter(active=True).order_by("pk").first()
    if configuration:
        return configuration.estimated_eur_per_1000_characters
    return settings.TTS_ESTIMATED_EUR_PER_1000_CHARACTERS


@never_cache
@login_required
def student_access_list(request):
    _require_teacher(request.user)
    accesses = list(
        _manageable_accesses(request.user)
        .prefetch_related("student__projects")
        .annotate(project_count=Count("student__projects"))
        .order_by("-created_at")
    )
    usage = _usage_by_student(accesses)
    now = timezone.now()
    for access in accesses:
        tts_usage = usage.get(access.student_id, {}).get(UsageEvent.Provider.ELEVENLABS, {})
        openai_usage = usage.get(access.student_id, {}).get(UsageEvent.Provider.OPENAI, {})
        access.characters_used = tts_usage.get("characters") or 0
        access.ai_requests_used = openai_usage.get("requests") or 0
        access.status = (
            "revoked"
            if access.revoked_at is not None or not access.student.is_active
            else "expired"
            if access.expires_at <= now
            else "active"
        )
    return render(
        request,
        "accounts/student_access_list.html",
        {
            "accesses": accesses,
            "active_count": sum(access.status == "active" for access in accesses),
        },
    )


@never_cache
@login_required
def student_access_create(request):
    _require_teacher(request.user)
    form = TemporaryStudentAccessForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        credentials = create_temporary_student_accesses(
            teacher=request.user,
            **form.cleaned_data,
        )
        character_total = form.cleaned_data["count"] * form.cleaned_data["character_limit"]
        estimated_cost = Decimal(character_total) / Decimal(1000) * _tts_estimated_rate()
        return render(
            request,
            "accounts/student_access_created.html",
            {
                "credentials": credentials,
                "login_url": request.build_absolute_uri(reverse("accounts:login")),
                "character_total": character_total,
                "estimated_cost": estimated_cost,
                "allow_ai": form.cleaned_data["allow_ai"],
            },
        )
    return render(
        request,
        "accounts/student_access_form.html",
        {
            "form": form,
            "estimated_rate": _tts_estimated_rate(),
        },
    )


@require_POST
@login_required
def student_access_revoke(request, access_id):
    _require_teacher(request.user)
    access = get_object_or_404(_manageable_accesses(request.user), pk=access_id)
    revoke_temporary_student_access(access)
    messages.success(request, f"Der Zugang „{access.label}“ wurde gesperrt.")
    return redirect("accounts:student_access_list")


@require_POST
@never_cache
@login_required
def student_access_reset_password(request, access_id):
    _require_teacher(request.user)
    access = get_object_or_404(_manageable_accesses(request.user), pk=access_id)
    if not access.is_usable:
        messages.error(request, "Nur aktive Schülerzugänge können ein neues Passwort erhalten.")
        return redirect("accounts:student_access_list")
    password = reset_student_access_password(access)
    return render(
        request,
        "accounts/student_access_created.html",
        {
            "credentials": [
                {
                    "access": access,
                    "username": access.student.username,
                    "password": password,
                }
            ],
            "login_url": request.build_absolute_uri(reverse("accounts:login")),
            "character_total": access.student.character_limit,
            "estimated_cost": (
                Decimal(access.student.character_limit) / Decimal(1000) * _tts_estimated_rate()
            ),
            "allow_ai": access.student.openai_daily_request_limit > 0,
            "password_reset": True,
        },
    )
