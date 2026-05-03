from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import DoctorProfile
from .models import Appointment, AppointmentCancellation, AppointmentSlot
from .services import AppointmentCancellationNotAllowed, cancel_patient_appointment, create_pending_appointment

User = get_user_model()


class AppointmentBookingValidationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.patient_one = User.objects.create_user(
            username="patient_one",
            password="password123",
            role=User.Role.PATIENT,
        )
        self.patient_two = User.objects.create_user(
            username="patient_two",
            password="password123",
            role=User.Role.PATIENT,
        )
        self.doctor_one = User.objects.create_user(
            username="doctor_one",
            password="password123",
            role=User.Role.DOCTOR,
        )
        self.doctor_two = User.objects.create_user(
            username="doctor_two",
            password="password123",
            role=User.Role.DOCTOR,
        )
        DoctorProfile.objects.create(
            user=self.doctor_one,
            specialty="Cardiology",
            bio="Doctor one",
            consultation_fee=Decimal("300.00"),
        )
        DoctorProfile.objects.create(
            user=self.doctor_two,
            specialty="Dermatology",
            bio="Doctor two",
            consultation_fee=Decimal("350.00"),
        )
        self.future_date = timezone.localdate() + timedelta(days=1)

    def create_slot(self, doctor, start_time, end_time):
        return AppointmentSlot.objects.create(
            doctor=doctor,
            date=self.future_date,
            start_time=start_time,
            end_time=end_time,
            is_booked=False,
        )

    def test_two_patients_cannot_book_same_doctor_slot(self):
        slot = self.create_slot(self.doctor_one, "10:00:00", "10:30:00")

        self.client.force_login(self.patient_one)
        first_response = self.client.post(reverse("book-appointment", args=[slot.id]))
        self.assertEqual(first_response.status_code, 200)

        self.client.force_login(self.patient_two)
        second_response = self.client.post(reverse("book-appointment", args=[slot.id]))
        self.assertEqual(second_response.status_code, 400)
        self.assertEqual(
            second_response.json()["error"],
            "This time slot is already booked for this doctor.",
        )

        self.assertEqual(Appointment.objects.active().filter(slot=slot).count(), 1)

    def test_same_patient_cannot_book_overlapping_times_with_different_doctors(self):
        first_slot = self.create_slot(self.doctor_one, "10:00:00", "10:30:00")
        overlapping_slot = self.create_slot(self.doctor_two, "10:15:00", "10:45:00")

        create_pending_appointment(patient=self.patient_one, slot_id=first_slot.id)

        with self.assertRaisesMessage(
            ValidationError,
            "You already have another active appointment that overlaps with this time.",
        ):
            create_pending_appointment(patient=self.patient_one, slot_id=overlapping_slot.id)

    def test_same_patient_cannot_book_second_slot_with_same_doctor_on_same_day(self):
        first_slot = self.create_slot(self.doctor_one, "13:00:00", "13:30:00")
        second_slot = self.create_slot(self.doctor_one, "14:00:00", "14:30:00")

        create_pending_appointment(patient=self.patient_one, slot_id=first_slot.id)

        with self.assertRaisesMessage(
            ValidationError,
            "You already have an active appointment with this doctor on this day.",
        ):
            create_pending_appointment(patient=self.patient_one, slot_id=second_slot.id)

    def test_cancelled_and_completed_appointments_do_not_block_new_booking(self):
        cancelled_slot = self.create_slot(self.doctor_one, "11:00:00", "11:30:00")
        completed_slot = self.create_slot(self.doctor_one, "12:00:00", "12:30:00")
        new_same_slot = cancelled_slot
        overlapping_new_slot = self.create_slot(self.doctor_two, "12:15:00", "12:45:00")

        cancelled_appointment = Appointment.objects.create(
            patient=self.patient_one,
            doctor=self.doctor_one,
            slot=cancelled_slot,
            status=Appointment.Status.CANCELLED,
        )
        completed_appointment = Appointment.objects.create(
            patient=self.patient_one,
            doctor=self.doctor_one,
            slot=completed_slot,
            status=Appointment.Status.COMPLETED,
        )

        cancelled_appointment.refresh_from_db()
        completed_appointment.refresh_from_db()
        self.assertIsNone(cancelled_appointment.active_slot)
        self.assertIsNone(completed_appointment.active_slot)

        replacement = create_pending_appointment(patient=self.patient_two, slot_id=new_same_slot.id)
        overlapping = create_pending_appointment(
            patient=self.patient_one,
            slot_id=overlapping_new_slot.id,
        )
        same_doctor_new_slot = self.create_slot(self.doctor_one, "15:00:00", "15:30:00")
        same_doctor_replacement = create_pending_appointment(
            patient=self.patient_one,
            slot_id=same_doctor_new_slot.id,
        )

        self.assertEqual(replacement.status, Appointment.Status.AWAITING_PAYMENT)
        self.assertEqual(overlapping.status, Appointment.Status.AWAITING_PAYMENT)
        self.assertEqual(same_doctor_replacement.status, Appointment.Status.AWAITING_PAYMENT)

    def test_patient_can_cancel_requested_or_confirmed_and_reason_is_saved(self):
        slot = self.create_slot(self.doctor_one, "16:00:00", "16:30:00")
        appointment = Appointment.objects.create(
            patient=self.patient_one,
            doctor=self.doctor_one,
            slot=slot,
            status=Appointment.Status.CONFIRMED,
        )
        slot.is_booked = True
        slot.save(update_fields=["is_booked"])

        cancel_patient_appointment(
            appointment_id=appointment.id,
            patient=self.patient_one,
            reason="I can no longer attend.",
        )

        appointment.refresh_from_db()
        slot.refresh_from_db()
        cancellation = AppointmentCancellation.objects.get(appointment=appointment)

        self.assertEqual(appointment.status, Appointment.Status.CANCELLED)
        self.assertFalse(slot.is_booked)
        self.assertEqual(cancellation.previous_status, Appointment.Status.CONFIRMED)
        self.assertEqual(cancellation.reason, "I can no longer attend.")
        self.assertEqual(cancellation.cancelled_by, self.patient_one)

    def test_patient_cannot_cancel_awaiting_payment_or_completed(self):
        slots_by_status = {
            Appointment.Status.AWAITING_PAYMENT: self.create_slot(self.doctor_one, "17:00:00", "17:30:00"),
            Appointment.Status.COMPLETED: self.create_slot(self.doctor_one, "18:00:00", "18:30:00"),
        }
        for status, slot in slots_by_status.items():
            with self.subTest(status=status):
                appointment = Appointment.objects.create(
                    patient=self.patient_one,
                    doctor=self.doctor_one,
                    slot=slot,
                    status=status,
                )

                with self.assertRaisesMessage(
                    AppointmentCancellationNotAllowed,
                    "You can cancel only requested or confirmed appointments.",
                ):
                    cancel_patient_appointment(
                        appointment_id=appointment.id,
                        patient=self.patient_one,
                        reason="Cannot attend.",
                    )

                appointment.refresh_from_db()
                self.assertEqual(appointment.status, status)
                self.assertFalse(AppointmentCancellation.objects.filter(appointment=appointment).exists())

    def test_cancel_view_requires_reason_and_owns_appointment(self):
        slot = self.create_slot(self.doctor_one, "19:00:00", "19:30:00")
        appointment = Appointment.objects.create(
            patient=self.patient_one,
            doctor=self.doctor_one,
            slot=slot,
            status=Appointment.Status.REQUESTED,
        )

        self.client.force_login(self.patient_one)
        response = self.client.post(reverse("cancel-appointment", args=[appointment.id]), {"reason": ""})
        self.assertRedirects(response, reverse("my-appointments"))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.REQUESTED)

        self.client.force_login(self.patient_two)
        response = self.client.post(
            reverse("cancel-appointment", args=[appointment.id]),
            {"reason": "Not my appointment."},
        )
        self.assertEqual(response.status_code, 404)
