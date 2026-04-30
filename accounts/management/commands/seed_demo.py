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

        # Profiles
        DoctorProfile.objects.get_or_create(
            user=doctor_1,
            defaults={
                "specialty": "Cardiology",
                "bio": "Experienced cardiologist with a focus on preventive care.",
            },
        )
        DoctorProfile.objects.get_or_create(
            user=doctor_2,
            defaults={
                "specialty": "Dermatology",
                "bio": "Skin health and cosmetic dermatology consultations.",
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

        # Doctor schedules (Mon-Fri)
        self._ensure_default_schedule(doctor_1)
        self._ensure_default_schedule(doctor_2)

        # Generate slots for the next N days based on schedules
        today = timezone.localdate()
        self._generate_slots_for_doctor(doctor_1, today, days)
        self._generate_slots_for_doctor(doctor_2, today, days)

        # Create a mix of appointments (past + future) and connected records
        self._seed_appointments(patient_1, doctor_1, today)
        self._seed_appointments(patient_2, doctor_2, today)

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
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": username,
                "role": role,
                "is_staff": is_staff,
                "is_superuser": is_superuser,
                "first_name": first_name,
                "last_name": last_name,
            },
        )

        changed = False
        if user.username != username:
            user.username = username
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
            DoctorSchedule.objects.get_or_create(
                doctor=doctor,
                day_of_week=dow,
                defaults={
                    "start_time": timezone.datetime(2000, 1, 1, 9, 0).time(),
                    "end_time": timezone.datetime(2000, 1, 1, 17, 0).time(),
                    "slot_duration_minutes": 30,
                },
            )

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

        # Notifications per patient
        Notification.objects.get_or_create(
            user=patient,
            message=f"Demo appointments ready for {patient.username}.",
            defaults={"is_read": False},
        )
