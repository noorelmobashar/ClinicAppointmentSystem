from django import forms
from django.forms import inlineformset_factory, modelformset_factory
from .models import Consultation, Prescription
from appointments.models import DoctorSchedule


class ConsultationForm(forms.ModelForm):
    class Meta:
        model = Consultation
        fields = ["symptoms_notes", "diagnosis"]
        widgets = {
            "symptoms_notes": forms.Textarea(attrs={"rows": 4}),
            "diagnosis": forms.Textarea(attrs={"rows": 4}),
        }


PrescriptionFormSet = inlineformset_factory(
    Consultation,
    Prescription,
    fields=["medication_name", "dosage", "duration"],
    extra=1,
    can_delete=True,
)

DoctorScheduleFormSet = modelformset_factory(
    DoctorSchedule,
    fields=["schedule_date", "start_time", "end_time", "slot_duration_minutes"],
    extra=1,
    can_delete=True,
    widgets={"schedule_date": forms.DateInput(attrs={"type": "date"})},
)
