from django.urls import path

from . import views

app_name = "script_assistant"

urlpatterns = [
    path("<uuid:conversation_id>/", views.conversation_detail, name="conversation"),
    path("<uuid:conversation_id>/ueberarbeiten/", views.conversation_refine, name="refine"),
    path("<uuid:conversation_id>/uebernehmen/", views.conversation_apply, name="apply"),
    path("<uuid:conversation_id>/verwerfen/", views.conversation_discard, name="discard"),
    path("projekt/<uuid:project_id>/ueberarbeiten/", views.project_revision, name="project_revision"),
    path("vorschlag/<uuid:proposal_id>/rueckgaengig/", views.proposal_undo, name="undo"),
]
