from django.urls import path
from .views import available_slots, book_appointment, patient_history

urlpatterns = [
    path("slots/", available_slots),
    path("book/<int:slot_id>/", book_appointment),
    path("my/", patient_history),
]