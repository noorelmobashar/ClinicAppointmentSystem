from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import uuid

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import DoctorProfile, PatientProfile
from appointments.models import Appointment, AppointmentSlot, DoctorSchedule
from appointments.services import generate_slots
from emr.models import Consultation, Prescription
from notifications.models import Notification
from payments.models import PaymentTransaction
from reception.models import WalkInPatient


class Command(BaseCommand):
    help = "Seed demo data for local testing (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default="123456",
            help="Password to set for all seeded users (default: 123456)",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="How many days of slots to generate (default: 7)",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password: str = options["password"]
        days: int = options["days"]

        User = get_user_model()

        # Users
        admin_user = self._get_or_create_user(
            User,
            username="admin",
            email="admin@test.com",
            role="ADMIN",
            password=password,
            is_staff=True,
            is_superuser=True,
            first_name="System",
            last_name="Admin",
        )

        receptionist = self._get_or_create_user(
            User,
            username="reception",
            email="reception@test.com",
            role="RECEPTIONIST",
            password=password,
            first_name="Rania",
            last_name="Reception",
        )

        doctor_1 = self._get_or_create_user(
            User,
            username="doctor",
            email="doctor@test.com",
            role="DOCTOR",
            password=password,
            first_name="Omar",
            last_name="Doctor",
        )

        doctor_2 = self._get_or_create_user(
            User,
            username="doctor2",
            email="doctor2@test.com",
            role="DOCTOR",
            password=password,
            first_name="Mona",
            last_name="Doctor",
        )

        doctor_3 = self._get_or_create_user(
            User,
            username="doctor3",
            email="doctor3@test.com",
            role="DOCTOR",
            password=password,
            first_name="Karim",
            last_name="Doctor",
        )

        patient_1 = self._get_or_create_user(
            User,
            username="patient",
            email="patient@test.com",
            role="PATIENT",
            password=password,
            first_name="Ali",
            last_name="Patient",
        )

        patient_2 = self._get_or_create_user(
            User,
            username="patient2",
            email="patient2@test.com",
            role="PATIENT",
            password=password,
            first_name="Sara",
            last_name="Patient",
        )
        patient_3 = self._get_or_create_user(
            User,
            username="patient3",
            email="patient3@test.com",
            role="PATIENT",
            password=password,
            first_name="Mariam",
            last_name="Patient",
        )

        # Profiles
        DoctorProfile.objects.get_or_create(
            user=doctor_1,
            defaults={
                "specialty": "Cardiology",
                "bio": "Experienced cardiologist with a focus on preventive care.",
                "consultation_fee": Decimal("250.00"),
            },
        )
        DoctorProfile.objects.get_or_create(
            user=doctor_2,
            defaults={
                "specialty": "Dermatology",
                "bio": "Skin health and cosmetic dermatology consultations.",
                "consultation_fee": Decimal("180.00"),
            },
        )
        DoctorProfile.objects.get_or_create(
            user=doctor_3,
            defaults={
                "specialty": "Internal Medicine",
                "bio": "General internal medicine and follow-up care.",
                "consultation_fee": Decimal("200.00"),
            },
        )

        PatientProfile.objects.get_or_create(
            user=patient_1,
            defaults={
                "date_of_birth": date(1998, 5, 12),
                "blood_type": "A+",
            },
        )
        PatientProfile.objects.get_or_create(
            user=patient_2,
            defaults={
                "date_of_birth": date(2001, 2, 1),
                "blood_type": "O+",
            },
        )
        PatientProfile.objects.get_or_create(
            user=patient_3,
            defaults={
                "date_of_birth": date(1995, 11, 20),
                "blood_type": "B+",
            },
        )

        # Doctor schedules (Mon-Fri)
        self._ensure_default_schedule(doctor_1)
        self._ensure_default_schedule(doctor_2)
        self._ensure_default_schedule(doctor_3)

        # Generate slots for the next N days based on schedules
        today = timezone.localdate()
        self._generate_slots_for_doctor(doctor_1, today, days)
        self._generate_slots_for_doctor(doctor_2, today, days)
        self._generate_slots_for_doctor(doctor_3, today, days)

        # Create a mix of appointments (past + future) and connected records
        self._seed_appointments(patient_1, doctor_1, today)
        self._seed_appointments(patient_2, doctor_2, today)
        self._seed_appointments(patient_3, doctor_3, today)
        self._seed_reception_today_queue(
            today=today,
            doctor_1=doctor_1,
            doctor_2=doctor_2,
            patient_1=patient_1,
            patient_2=patient_2,
            patient_3=patient_3,
        )

        # Walk-in patients for reception testing
        WalkInPatient.objects.get_or_create(
            name="Walk-in Ahmed",
            phone_number="01000000001",
            defaults={"notes": "Requested urgent consultation."},
        )
        WalkInPatient.objects.get_or_create(
            name="Walk-in Nour",
            phone_number="01000000002",
            defaults={"notes": "First visit, no prior history."},
        )

        # Notifications
        Notification.objects.get_or_create(
            user=admin_user,
            message="Demo seed completed successfully.",
            defaults={"is_read": False},
        )
        Notification.objects.get_or_create(
            user=receptionist,
            message="2 walk-in patients added for today's queue.",
            defaults={"is_read": False},
        )
        Notification.objects.get_or_create(
            user=doctor_1,
            message="Demo: new appointment requests are waiting for review.",
            defaults={"is_read": True},
        )

        self.stdout.write(self.style.SUCCESS("Demo data seeded."))

    def _get_or_create_user(
        self,
        User,
        *,
        username: str,
        email: str,
        role: str,
        password: str,
        is_staff: bool = False,
        is_superuser: bool = False,
        first_name: str = "",
        last_name: str = "",
    ):
        # Ensure the desired username is available; if taken by another email, find a unique one
        uname = username
        if User.objects.filter(username=uname).exclude(email=email).exists():
            suffix = 2
            while User.objects.filter(username=f"{uname}{suffix}").exists():
                suffix += 1
            uname = f"{uname}{suffix}"

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": uname,
                "role": role,
                "is_staff": is_staff,
                "is_superuser": is_superuser,
                "first_name": first_name,
                "last_name": last_name,
            },
        )

        changed = False
        # Ensure stored username matches the (possibly adjusted) uname we used on creation
        if user.username != uname:
            user.username = uname
            changed = True
        if user.role != role:
            user.role = role
            changed = True
        if user.is_staff != is_staff:
            user.is_staff = is_staff
            changed = True
        if user.is_superuser != is_superuser:
            user.is_superuser = is_superuser
            changed = True
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if last_name and user.last_name != last_name:
            user.last_name = last_name
            changed = True

        # Always ensure password is known for demo users
        user.set_password(password)
        changed = True

        if created or changed:
            user.save()

        return user

    def _ensure_default_schedule(self, doctor):
        # Mon-Fri 09:00 to 17:00, 30-minute slots
        for dow in range(0, 5):
            default_start = timezone.datetime(2000, 1, 1, 9, 0).time()
            default_end = timezone.datetime(2000, 1, 1, 17, 0).time()
            default_duration = 30

            schedules_qs = DoctorSchedule.objects.filter(doctor=doctor, day_of_week=dow).order_by("id")
            schedule = schedules_qs.first()

            if schedule is None:
                DoctorSchedule.objects.create(
                    doctor=doctor,
                    day_of_week=dow,
                    start_time=default_start,
                    end_time=default_end,
                    slot_duration_minutes=default_duration,
                )
                continue

            extra_ids = list(schedules_qs.values_list("id", flat=True)[1:])
            if extra_ids:
                DoctorSchedule.objects.filter(id__in=extra_ids).delete()

            updated_fields = []
            if schedule.start_time != default_start:
                schedule.start_time = default_start
                updated_fields.append("start_time")
            if schedule.end_time != default_end:
                schedule.end_time = default_end
                updated_fields.append("end_time")
            if schedule.slot_duration_minutes != default_duration:
                schedule.slot_duration_minutes = default_duration
                updated_fields.append("slot_duration_minutes")

            if updated_fields:
                schedule.save(update_fields=updated_fields)

    def _generate_slots_for_doctor(self, doctor, start_day: date, days: int):
        schedules = DoctorSchedule.objects.filter(doctor=doctor)
        for i in range(days):
            d = start_day + timedelta(days=i)
            dow = d.weekday()  # Monday=0
            for schedule in schedules.filter(day_of_week=dow):
                generate_slots(schedule, d)

    def _seed_appointments(self, patient, doctor, today: date):
        # Pick a past slot for completed/paid appointment
        past_day = today - timedelta(days=2)
        past_slot = (
            AppointmentSlot.objects.filter(doctor=doctor, date=past_day)
            .order_by("start_time")
            .first()
        )
        if past_slot:
            appt, created = Appointment.objects.get_or_create(
                patient=patient,
                slot=past_slot,
                defaults={
                    "doctor": doctor,
                    "status": Appointment.Status.COMPLETED,
                },
            )
            if created:
                past_slot.is_booked = True
                past_slot.save(update_fields=["is_booked"])

            # EMR
            consult, _ = Consultation.objects.get_or_create(
                appointment=appt,
                defaults={
                    "doctor": doctor,
                    "patient": patient,
                    "symptoms_notes": "Headache and fatigue for 3 days.",
                    "diagnosis": "General check-up; advised rest and hydration.",
                },
            )
            Prescription.objects.get_or_create(
                consultation=consult,
                medication_name="Paracetamol",
                defaults={
                    "dosage": "500mg",
                    "duration": "3 days",
                },
            )

            # Payment
            PaymentTransaction.objects.get_or_create(
                appointment=appt,
                defaults={
                    "stripe_checkout_id": f"demo_{uuid.uuid4().hex}",
                    "amount": Decimal("200.00"),
                    "status": PaymentTransaction.Status.PAID,
                },
            )

        # Pick a future slot for awaiting payment
        future_day = today + timedelta(days=1)
        future_slot = (
            AppointmentSlot.objects.filter(doctor=doctor, date=future_day, is_booked=False)
            .order_by("start_time")
            .first()
        )
        if future_slot:
            appt, created = Appointment.objects.get_or_create(
                patient=patient,
                slot=future_slot,
                defaults={
                    "doctor": doctor,
                    "status": Appointment.Status.AWAITING_PAYMENT,
                },
            )
            if created:
                future_slot.is_booked = True
                future_slot.save(update_fields=["is_booked"])

            PaymentTransaction.objects.get_or_create(
                appointment=appt,
                defaults={
                    "stripe_checkout_id": f"demo_{uuid.uuid4().hex}",
                    "amount": Decimal("250.00"),
                    "status": PaymentTransaction.Status.PENDING,
                },
            )

        # Pick another future slot for requested appointment
        requested_day = today + timedelta(days=2)
        requested_slot = (
            AppointmentSlot.objects.filter(doctor=doctor, date=requested_day, is_booked=False)
            .order_by("start_time")
            .first()
        )
        if requested_slot:
            appt, created = Appointment.objects.get_or_create(
                patient=patient,
                slot=requested_slot,
                defaults={
                    "doctor": doctor,
                    "status": Appointment.Status.REQUESTED,
                },
            )
            if created:
                requested_slot.is_booked = True
                requested_slot.save(update_fields=["is_booked"])

        # Pick another future slot for cancelled appointment with a failed payment record
        cancelled_day = today + timedelta(days=3)
        cancelled_slot = (
            AppointmentSlot.objects.filter(doctor=doctor, date=cancelled_day, is_booked=False)
            .order_by("start_time")
            .first()
        )
        if cancelled_slot:
            appt, created = Appointment.objects.get_or_create(
                patient=patient,
                slot=cancelled_slot,
                defaults={
                    "doctor": doctor,
                    "status": Appointment.Status.CANCELLED,
                },
            )
            if created:
                cancelled_slot.is_booked = True
                cancelled_slot.save(update_fields=["is_booked"])

            PaymentTransaction.objects.get_or_create(
                appointment=appt,
                defaults={
                    "stripe_checkout_id": f"demo_{uuid.uuid4().hex}",
                    "amount": Decimal("150.00"),
                    "status": PaymentTransaction.Status.FAILED,
                },
            )

        # Notifications per patient
        Notification.objects.get_or_create(
            user=patient,
            message=f"Demo appointments ready for {patient.username}.",
            defaults={"is_read": False},
        )

    def _seed_reception_today_queue(self, *, today, doctor_1, doctor_2, patient_1, patient_2, patient_3):
        """Seed same-day reception statuses for dashboard flow testing."""
        doctor_1_slots = list(
            AppointmentSlot.objects.filter(doctor=doctor_1, date=today, is_booked=False)
            .order_by("start_time")[:2]
        )
        doctor_2_slots = list(
            AppointmentSlot.objects.filter(doctor=doctor_2, date=today, is_booked=False)
            .order_by("start_time")[:2]
        )

        slot_1 = doctor_1_slots[0] if len(doctor_1_slots) > 0 else None
        slot_2 = doctor_1_slots[1] if len(doctor_1_slots) > 1 else None
        slot_3 = doctor_2_slots[0] if len(doctor_2_slots) > 0 else None
        slot_4 = doctor_2_slots[1] if len(doctor_2_slots) > 1 else None

        self._upsert_today_appointment(patient_1, doctor_1, slot_1, Appointment.Status.CONFIRMED)
        self._upsert_today_appointment(patient_2, doctor_1, slot_2, Appointment.Status.CONFIRMED)
        self._upsert_today_appointment(patient_3, doctor_2, slot_3, Appointment.Status.CHECKED_IN)
        self._upsert_today_appointment(patient_1, doctor_2, slot_4, Appointment.Status.CONFIRMED)

    def _upsert_today_appointment(self, patient, doctor, slot, status):
        if not slot:
            return

        appointment, created = Appointment.objects.get_or_create(
            patient=patient,
            slot=slot,
            defaults={
                "doctor": doctor,
                "status": status,
            },
        )
        if not created and appointment.status != status:
            appointment.status = status
            appointment.doctor = doctor
            appointment.save(update_fields=["status", "doctor"])

        if not slot.is_booked:
            slot.is_booked = True
            slot.save(update_fields=["is_booked"])
