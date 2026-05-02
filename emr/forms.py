from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory, modelformset_factory
from .models import Consultation, Prescription
from appointments.models import DoctorSchedule


class ConsultationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["symptoms_notes"].required = True
        self.fields["diagnosis"].required = True

    class Meta:
        model = Consultation
        fields = ["symptoms_notes", "diagnosis"]
        widgets = {
            "symptoms_notes": forms.Textarea(attrs={"rows": 4}),
            "diagnosis": forms.Textarea(attrs={"rows": 4}),
        }


class RequiredPrescriptionFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        active_forms = [
            form
            for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False)
        ]
        if not active_forms:
            raise forms.ValidationError("Add at least one prescription.")


PrescriptionFormSet = inlineformset_factory(
    Consultation,
    Prescription,
    formset=RequiredPrescriptionFormSet,
    fields=["medication_name", "dosage", "duration"],
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)

DoctorScheduleFormSet = modelformset_factory(
    DoctorSchedule,
    fields=["schedule_date", "start_time", "end_time", "slot_duration_minutes"],
    extra=1,
    can_delete=True,
    widgets={"schedule_date": forms.DateInput(attrs={"type": "date"})},
)
