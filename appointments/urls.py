from django.urls import path
from .views import (
    available_slots,
    book_appointment,
    cancel_appointment,
    cancel_appointment_preflight,
    doctor_profile_detail,
    patient_booking,
    patient_history,
)

urlpatterns = [
    path("slots/", available_slots, name="available-slots"),
    path("book/", patient_booking, name="patient-booking"),
    path("book/<int:slot_id>/", book_appointment, name="book-appointment"),
    path("my/<int:appointment_id>/cancel/preflight/", cancel_appointment_preflight, name="cancel-appointment-preflight"),
    path("my/<int:appointment_id>/cancel/", cancel_appointment, name="cancel-appointment"),
    path("doctors/<int:doctor_id>/profile/", doctor_profile_detail, name="doctor-public-profile"),
    path("my/", patient_history, name="my-appointments"),
]
