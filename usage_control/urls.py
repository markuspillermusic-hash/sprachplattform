from django.urls import path
from .views import overview

app_name = 'usage_control'
urlpatterns = [path('', overview, name='overview')]
