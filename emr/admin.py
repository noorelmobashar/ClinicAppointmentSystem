from django.contrib import admin
from .models import Consultation, Prescription


@admin.register(Consultation)
class ConsultationAdmin(admin.ModelAdmin):
    list_display = ["patient", "doctor", "appointment"]
    list_filter = ["doctor"]
    search_fields = ["patient__username", "patient__first_name", "patient__last_name"]


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ["medication_name", "consultation", "dosage"]
    search_fields = ["medication_name"]
