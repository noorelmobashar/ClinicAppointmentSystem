from django.conf import settings
from django.db import models


class Consultation(models.Model):
    appointment = models.OneToOneField(
        "appointments.Appointment",
        on_delete=models.CASCADE,
        related_name="consultation",
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="doctor_consultations",
    )
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patient_consultations",
    )
    symptoms_notes = models.TextField(blank=True)
    diagnosis = models.TextField(blank=True)

    def __str__(self):
        return f"Consultation for {self.patient}"


class Prescription(models.Model):
    consultation = models.ForeignKey(
        Consultation,
        on_delete=models.CASCADE,
        related_name="prescriptions",
    )
    medication_name = models.CharField(max_length=150)
    dosage = models.CharField(max_length=100)
    duration = models.CharField(max_length=100)

    def __str__(self):
        return self.medication_name
