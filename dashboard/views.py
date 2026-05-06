from datetime import date as date_class, timedelta

from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone

from appointments.models import Appointment
from reception.models import WalkInPatient
from accounts.models import CustomUser
from accounts.utils.profile_completion import is_profile_complete
from admin_panel.views import get_analytics_data

class DashboardView(LoginRequiredMixin, View):
    def get(self, request):
        if not is_profile_complete(request.user):
            return redirect("onboarding")
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

        # Doctor summary
        if request.user.role == "DOCTOR":
            today = timezone.now().date()
            
            # Calculate week start (Monday) and end (Sunday)
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            
            # Get all appointments for this doctor in the current week
            doctor_weekly_appointments = Appointment.objects.filter(
                slot__doctor=request.user,
                slot__date__gte=week_start,
                slot__date__lte=week_end,
            ).select_related("patient", "slot").order_by("slot__date", "slot__start_time")
            
            # Get today's appointments specifically
            doctor_today_appointments = doctor_weekly_appointments.filter(
                slot__date=today
            )
            
            # Calculate metrics
            total_weekly = doctor_weekly_appointments.count()
            total_today = doctor_today_appointments.count()
            pending_today = doctor_today_appointments.filter(
                status=Appointment.Status.REQUESTED
            ).count()
            confirmed_today = doctor_today_appointments.filter(
                status=Appointment.Status.CONFIRMED
            ).count()
            checked_in_today = doctor_today_appointments.filter(
                status=Appointment.Status.CHECKED_IN
            ).count()
            completed_today = doctor_today_appointments.filter(
                status=Appointment.Status.COMPLETED
            ).count()
            
            context.update({
                "dashboard_title": "Your clinical overview",
                "dashboard_subtitle": "Monitor your weekly schedule, today's queue, and patient progress through consultations.",
                "today": today,
                "week_start": week_start,
                "week_end": week_end,
                "weekly_appointments": doctor_weekly_appointments,
                "today_appointments": doctor_today_appointments,
                "patients_today": total_today,
                "pending_consultations": pending_today,
                "completed_consultations": completed_today,
                "active_consultations": checked_in_today,
                "confirmed_consultations": confirmed_today,
                "total_weekly": total_weekly,
            })

        if request.user.role == "RECEPTIONIST":
            today = timezone.now().date()
            appointments_qs = Appointment.objects.select_related(
                'patient',
                'slot',
                'slot__doctor',
                'slot__doctor__doctor_profile',
            ).order_by('slot__start_time')

            doctor_filter = request.GET.get('doctor') or ''
            date_filter = request.GET.get('date_filter') or today.isoformat()
            search_query = (request.GET.get('q') or '').strip()

            if date_filter == 'all':
                date_filter = ''

            if doctor_filter:
                appointments_qs = appointments_qs.filter(slot__doctor_id=doctor_filter)

            if date_filter and date_filter != 'all':
                try:
                    selected_date = date_class.fromisoformat(date_filter)
                except ValueError:
                    selected_date = today

                if selected_date:
                    appointments_qs = appointments_qs.filter(slot__date=selected_date)
                else:
                    date_filter = ''

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

            if search_query:
                lower_q = search_query.lower()
                appointments = [a for a in appointments if lower_q in (a.display_patient_name or "").lower()]

            context.update({
                'appointments': appointments,
                'walkins': walkins_qs,
                'doctors': CustomUser.objects.filter(role='DOCTOR'),
                'today': today,
                'total_patients_today': appointments_qs.count(),
                'pending_patients': appointments_qs.filter(status=Appointment.Status.CONFIRMED).count(),
                'checked_in_patients': appointments_qs.filter(status=Appointment.Status.CHECKED_IN).count(),
                'active_appointments': appointments_qs.exclude(status__in=[Appointment.Status.COMPLETED, Appointment.Status.CANCELLED]).count(),
                'selected_doctor': doctor_filter,
                'selected_date_filter': date_filter,
                'search_query': search_query,
            })

        if request.user.role == "ADMIN":
            
            # Date parsing
            date_from_str = self.request.GET.get('date_from')
            date_to_str = self.request.GET.get('date_to')
            
            if date_to_str:
                try:
                    date_to = timezone.datetime.strptime(date_to_str, '%Y-%m-%d').date()
                    date_to = timezone.make_aware(timezone.datetime.combine(date_to, timezone.datetime.max.time()))
                except ValueError:
                    date_to = timezone.now()
            else:
                date_to = timezone.now()
                
            if date_from_str:
                try:
                    date_from = timezone.datetime.strptime(date_from_str, '%Y-%m-%d').date()
                    date_from = timezone.make_aware(timezone.datetime.combine(date_from, timezone.datetime.min.time()))
                except ValueError:
                    date_from = date_to - timedelta(days=365)
            else:
                date_from = date_to - timedelta(days=365)

            context.update(get_analytics_data(date_from, date_to))
            context.update({
                "dashboard_title": "Admin Control Center",
                "dashboard_subtitle": "Overview of clinic activity and user management.",
                "date_from": date_from.strftime('%Y-%m-%d'),
                "date_to": date_to.strftime('%Y-%m-%d'),
            })
        return render(request, 'dashboard/dashboard.html', context)
