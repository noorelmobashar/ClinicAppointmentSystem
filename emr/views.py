from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import ListView, View

from appointments.models import Appointment, DoctorSchedule
from .models import Consultation
from .forms import ConsultationForm, PrescriptionFormSet, DoctorScheduleFormSet


class DoctorRequiredMixin(LoginRequiredMixin):
    """Check that user is a doctor."""
    def dispatch(self, request, *args, **kwargs):
        if request.user.role != "DOCTOR":
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class DoctorDailyQueueView(DoctorRequiredMixin, ListView):
    """Show today's checked-in patients."""
    template_name = "emr/daily_queue.html"
    context_object_name = "appointments"
    paginate_by = 20

    def get_queryset(self):
        today = timezone.now().date()
        return Appointment.objects.filter(
            slot__doctor=self.request.user,
            slot__date=today,
            status=Appointment.Status.CHECKED_IN,
        ).select_related("patient", "slot").order_by("slot__start_time")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        context["today"] = today
        context["completed_today"] = Appointment.objects.filter(
            slot__doctor=self.request.user,
            slot__date=today,
            status=Appointment.Status.COMPLETED,
        ).count()
        return context


class ConsultationCreateView(DoctorRequiredMixin, View):
    """Create consultation and prescriptions, mark appointment as COMPLETED."""
    template_name = "emr/consultation_form.html"

    def get_appointment(self):
        appointment_id = self.kwargs["appointment_id"]
        return get_object_or_404(
            Appointment,
            pk=appointment_id,
            slot__doctor=self.request.user,
            status=Appointment.Status.CHECKED_IN,
        )

    def get(self, request, *args, **kwargs):
        appointment = self.get_appointment()
        form = ConsultationForm()
        formset = PrescriptionFormSet()

        return render(request, self.template_name, {
            "appointment": appointment,
            "form": form,
            "formset": formset,
        })

    def post(self, request, *args, **kwargs):
        appointment = self.get_appointment()
        form = ConsultationForm(request.POST)
        formset = PrescriptionFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            return self.save_consultation(appointment, form, formset)

        return render(request, self.template_name, {
            "appointment": appointment,
            "form": form,
            "formset": formset,
        })

    @transaction.atomic
    def save_consultation(self, appointment, form, formset):
        consultation = form.save(commit=False)
        consultation.appointment = appointment
        consultation.doctor = self.request.user
        consultation.patient = appointment.patient
        consultation.save()

        formset.instance = consultation
        formset.save()

        appointment.status = Appointment.Status.COMPLETED
        appointment.save()

        messages.success(self.request, f"Consultation saved for {appointment.patient}")
        return redirect("emr:daily-queue")


class ManageScheduleView(DoctorRequiredMixin, View):
    """Doctor manages their availability schedule."""
    template_name = "emr/manage_schedule.html"

    def get_queryset(self):
        return DoctorSchedule.objects.filter(doctor=self.request.user).order_by("day_of_week", "start_time")

    def get(self, request, *args, **kwargs):
        formset = DoctorScheduleFormSet(queryset=self.get_queryset())
        return render(request, self.template_name, {
            "formset": formset,
            "schedules": self.get_queryset(),
        })

    def post(self, request, *args, **kwargs):
        formset = DoctorScheduleFormSet(request.POST, queryset=self.get_queryset())

        if formset.is_valid():
            instances = formset.save(commit=False)
            for instance in instances:
                instance.doctor = request.user
                instance.save()

            for obj in formset.deleted_objects:
                obj.delete()

            messages.success(request, "Schedule updated.")
            return redirect("emr:manage-schedule")

        return render(request, self.template_name, {
            "formset": formset,
            "schedules": self.get_queryset(),
        })


class ConsultationListView(DoctorRequiredMixin, ListView):
    """Show all consultations for this doctor."""
    template_name = "emr/consultations_list.html"
    context_object_name = "consultations"
    paginate_by = 20

    def get_queryset(self):
        return Consultation.objects.filter(
            doctor=self.request.user
        ).select_related("patient", "appointment__slot").order_by("-id")
