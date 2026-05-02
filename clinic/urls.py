
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from clinic.views import favicon

urlpatterns = [
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
    path('favicon.ico', favicon),
    path('favicon.svg', favicon),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('appointments/', include('appointments.urls')),
    path('reception/', include('reception.urls')),
    path('emr/', include('emr.urls')),
    path('payments/', include('payments.urls')),
]
