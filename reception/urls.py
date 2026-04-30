from django.urls import path
from . import views

app_name = 'reception'

urlpatterns = [
	path('', views.FrontDeskTrafficView.as_view(), name='traffic_board'),
	path('update-status/<int:pk>/', views.UpdateAppointmentStatusView.as_view(), name='update_status'),
	path('walk-in/', views.ForceBookingView.as_view(), name='walk_in'),
]
