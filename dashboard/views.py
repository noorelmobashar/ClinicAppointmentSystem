from django.shortcuts import render
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone

from appointments.models import Appointment
from reception.models import WalkInPatient
from accounts.models import CustomUser
from reception.forms import WalkInPatientForm


class DashboardView(LoginRequiredMixin, View):
    def get(self, request):
        context = {
            "current_section": "overview",
        }

        # Patient summary
        if request.user.role == "PATIENT":
            today = timezone.now().date()
            patient_appointments = Appointment.objects.filter(
                patient=request.user
            ).select_related("doctor", "doctor__doctor_profile", "slot")
            upcoming_appointments = patient_appointments.filter(
                slot__date__gte=today
            ).order_by("slot__date", "slot__start_time")
            pending_statuses = [
                Appointment.Status.REQUESTED,
                Appointment.Status.AWAITING_PAYMENT,
            ]
            next_confirmed_visit = upcoming_appointments.filter(
                status=Appointment.Status.CONFIRMED
            ).first()
            context.update({
                "dashboard_title": "Your care overview",
                "dashboard_subtitle": "Track upcoming appointments, recent activity, and the next steps for your clinic visits.",
                "today": today,
                "total_appointments": patient_appointments.count(),
                "upcoming_appointments": upcoming_appointments.count(),
                "completed_visits": patient_appointments.filter(status=Appointment.Status.COMPLETED).count(),
                "active_appointments": patient_appointments.exclude(
                    status__in=[Appointment.Status.COMPLETED, Appointment.Status.CANCELLED]
                ).count(),
                "pending_approvals": patient_appointments.filter(status__in=pending_statuses).count(),
                "next_confirmed_visit": next_confirmed_visit,
                "recent_upcoming_appointments": upcoming_appointments[:3],
                "last_appointment": patient_appointments.order_by("-slot__date", "-slot__start_time").first(),
                "patient_profile": getattr(request.user, "patient_profile", None),
            })

        
        if request.user.role == "RECEPTIONIST":
            today = timezone.now().date()
            appointments_qs = Appointment.objects.filter(slot__date=today).select_related('patient', 'slot', 'slot__doctor').order_by('slot__start_time')
            walkins_qs = WalkInPatient.objects.filter(created_at__date=today)
            walkin_name_by_id = {walkin.id: walkin.name for walkin in walkins_qs}
            appointments = list(appointments_qs)

            for appointment in appointments:
                patient_name = (appointment.patient.get_full_name() or "").strip()
                if not patient_name:
                    username = (appointment.patient.username or "").strip()
                    if username.startswith("walkin_"):
                        try:
                            walkin_id = int(username.split("_", 1)[1])
                            patient_name = walkin_name_by_id.get(walkin_id, "")
                        except (TypeError, ValueError, IndexError):
                            patient_name = ""
                    appointment.display_patient_name = patient_name or username or "Unknown patient"
                else:
                    appointment.display_patient_name = patient_name

            context.update({
                'appointments': appointments,
                'walkins': walkins_qs,
                'doctors': CustomUser.objects.filter(role='DOCTOR'),
                'walkin_form': WalkInPatientForm(),
                'today': today,
                'total_patients_today': appointments_qs.count(),
                'pending_patients': appointments_qs.filter(status=Appointment.Status.CONFIRMED).count(),
                'checked_in_patients': appointments_qs.filter(
                    status=Appointment.Status.CHECKED_IN
                ).count(),
                'active_appointments': appointments_qs.exclude(
                    status__in=[Appointment.Status.COMPLETED, Appointment.Status.CANCELLED]
                ).count(),
            })

        return render(request, 'dashboard/dashboard.html', context)
