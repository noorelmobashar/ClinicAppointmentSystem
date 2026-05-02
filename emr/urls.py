from django.urls import path
from . import views

app_name = "emr"

urlpatterns = [
    path("queue/", views.DoctorDailyQueueView.as_view(), name="daily-queue"),
    path("consultations/", views.ConsultationListView.as_view(), name="consultations-list"),
    path("consultation/<int:appointment_id>/", views.ConsultationCreateView.as_view(), name="consultation-create"),
    path("schedule/", views.ManageScheduleView.as_view(), name="manage-schedule"),
]
