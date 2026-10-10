from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from .reporting import can_view_platform, personal_snapshot, platform_snapshot


@login_required
@never_cache
def overview(request):
    return render(request, 'usage_control/overview.html', {
        'quota': personal_snapshot(request.user),
        'platform_cards': platform_snapshot() if can_view_platform(request.user) else [],
    })
