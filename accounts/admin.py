from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User
from .services import reset_temporary_password


@admin.register(User)
class SprachplattformUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Sprachplattform", {"fields": ("role", "must_change_password", "character_limit")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Sprachplattform", {"fields": ("role", "must_change_password", "character_limit")}),
    )
    list_display = UserAdmin.list_display + ("role", "must_change_password", "character_limit")
    actions = ("issue_temporary_passwords",)

    @admin.action(description="Neue temporäre Passwörter erzeugen")
    def issue_temporary_passwords(self, request, queryset):
        credentials = [f"{user.username}: {reset_temporary_password(user)}" for user in queryset]
        self.message_user(
            request,
            "Nur jetzt sichtbar – sicher übermitteln: " + " · ".join(credentials),
        )
