from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'reception'

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='dashboard', permanent=False), name='traffic_board'),
    path('update-status/<int:pk>/', views.UpdateAppointmentStatusView.as_view(), name='update_status'),
    path('walk-in/', views.WalkInPatientCreateView.as_view(), name='walk_in'),
    path('reschedule/<int:pk>/', views.RescheduleAppointmentView.as_view(), name='reschedule'),
]
