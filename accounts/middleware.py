from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and user.must_change_password:
            allowed_paths = {
                reverse("accounts:password_change"),
                reverse("accounts:logout"),
            }
            if request.path not in allowed_paths and not request.path.startswith(("/static/", "/health/")):
                return redirect("accounts:password_change")
        return self.get_response(request)

