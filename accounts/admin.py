from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import TemporaryStudentAccess, User
from .services import reset_temporary_password


@admin.register(User)
class SprachplattformUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            "Sprachplattform",
            {
                "fields": (
                    "role",
                    "must_change_password",
                    "character_limit",
                    "openai_monthly_input_token_limit",
                    "openai_monthly_output_token_limit",
                    "openai_daily_request_limit",
                )
            },
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Sprachplattform",
            {
                "fields": (
                    "role",
                    "character_limit",
                ),
                "description": (
                    "Das oben vergebene Startpasswort ist frei wählbar. "
                    "Beim ersten Login muss der Nutzer ein eigenes Passwort festlegen."
                ),
            },
        ),
    )
    list_display = UserAdmin.list_display + (
        "role",
        "must_change_password",
        "character_limit",
        "openai_monthly_input_token_limit",
        "openai_monthly_output_token_limit",
    )
    actions = ("issue_temporary_passwords",)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.must_change_password = True
        super().save_model(request, obj, form, change)

    @admin.action(description="Neue temporäre Passwörter erzeugen")
    def issue_temporary_passwords(self, request, queryset):
        credentials = [f"{user.username}: {reset_temporary_password(user)}" for user in queryset]
        self.message_user(
            request,
            "Nur jetzt sichtbar – sicher übermitteln: " + " · ".join(credentials),
        )


@admin.register(TemporaryStudentAccess)
class TemporaryStudentAccessAdmin(admin.ModelAdmin):
    list_display = (
        "label",
        "student",
        "teacher",
        "expires_at",
        "status_display",
        "created_at",
    )
    list_filter = ("revoked_at", "expires_at", "created_at")
    search_fields = ("label", "student__username", "teacher__username")
    readonly_fields = (
        "teacher",
        "student",
        "label",
        "expires_at",
        "revoked_at",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    @admin.display(description="Status")
    def status_display(self, access):
        return access.status_label
