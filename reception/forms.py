from django import forms
from django.contrib.auth import get_user_model

from .models import WalkInPatient
from appointments.models import Appointment

User = get_user_model()


class WalkInPatientForm(forms.Form):
    name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            "class": "walkin-input",
            "placeholder": "Patient full name",
        }),
    )
    phone_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            "class": "walkin-input",
            "placeholder": "Phone number",
        }),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "class": "walkin-input walkin-textarea",
            "placeholder": "Optional notes",
            "rows": 3,
        }),
    )
    doctor = forms.ModelChoiceField(
        queryset=User.objects.filter(role='DOCTOR'),
        widget=forms.Select(attrs={"class": "walkin-input"}),
    )


class UpdateStatusForm(forms.Form):
    STATUS_CHOICES = [
        (Appointment.Status.CONFIRMED, 'Confirmed'),
        (Appointment.Status.CHECKED_IN, 'Checked In'),
        (Appointment.Status.COMPLETED, 'Completed'),
        (Appointment.Status.CANCELLED, 'Cancelled'),
    ]
    status = forms.ChoiceField(choices=STATUS_CHOICES)