
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from accounts.views import OnboardingView
from clinic.views import favicon
from django.conf import settings

urlpatterns = [
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
    path('onboarding/', OnboardingView.as_view(), name='onboarding'),
    path('favicon.ico', favicon),
    path('favicon.svg', favicon),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('appointments/', include('appointments.urls')),
    path('reception/', include('reception.urls')),
    path('emr/', include('emr.urls')),
    path('payments/', include('payments.urls')),
    path('admin-panel/', include('admin_panel.urls')),
    
    # path('__debug__/', include('debug_toolbar.urls')),
]


if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('debug/', include(debug_toolbar.urls)),
    ] + urlpatterns