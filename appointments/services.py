from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Appointment, AppointmentSlot, DoctorSchedule


def generate_slots(schedule, date):
    start = datetime.combine(date, schedule.start_time)
    end = datetime.combine(date, schedule.end_time)

    duration = timedelta(minutes=schedule.slot_duration_minutes)

    buffer = timedelta(minutes=5)

    current = start

    while current + duration <= end:
        slot_start = current.time()
        slot_end = (current + duration).time()

        exists = AppointmentSlot.objects.filter(
            doctor=schedule.doctor,
            date=date,
            start_time=slot_start
        ).exists()

        if not exists:
            AppointmentSlot.objects.create(
                doctor=schedule.doctor,
                date=date,
                start_time=slot_start,
                end_time=slot_end,
            )

        current += duration + buffer


def rebuild_doctor_weekday_slots(doctor, weekday, days_ahead=30):
    """
    Regenerate future unbooked slots for one doctor's weekday.
    Existing slots linked to appointments are preserved.
    """
    today = timezone.localdate()
    end_date = today + timedelta(days=days_ahead)

    AppointmentSlot.objects.filter(
        doctor=doctor,
        date__gte=today,
        date__lte=end_date,
        date__week_day=weekday + 2,
        appointments__isnull=True,
    ).delete()

    schedules = DoctorSchedule.objects.filter(
        doctor=doctor,
        day_of_week=weekday,
    )

    current_date = today
    while current_date <= end_date:
        if current_date.weekday() == weekday:
            for schedule in schedules:
                generate_slots(schedule, current_date)
        current_date += timedelta(days=1)


def sync_schedule_slots(schedule, days_ahead=30):
    rebuild_doctor_weekday_slots(
        doctor=schedule.doctor,
        weekday=schedule.day_of_week,
        days_ahead=days_ahead,
    )


def create_pending_appointment(*, patient, slot_id):
    """
    Create one pending appointment while preventing:
    - duplicate active bookings for the same slot
    - overlapping active appointments for the same patient

    The patient row and slot row are locked so concurrent booking attempts are
    serialized at the database level.
    """
    User = get_user_model()

    with transaction.atomic():
        User.objects.select_for_update().get(pk=patient.pk)
        slot = (
            AppointmentSlot.objects.select_for_update()
            .select_related("doctor")
            .get(pk=slot_id)
        )

        slot_datetime = timezone.make_aware(
            datetime.combine(slot.date, slot.start_time),
            timezone.get_current_timezone(),
        )
        if slot_datetime <= timezone.now():
            raise ValidationError("This time slot has already passed.")

        if slot.is_booked:
            raise ValidationError("The session is already booked by another user.")

        appointment = Appointment(
            patient=patient,
            doctor=slot.doctor,
            slot=slot,
            status=Appointment.Status.AWAITING_PAYMENT,
        )

        try:
            appointment.save()
        except IntegrityError as exc:
            if Appointment.objects.active().filter(slot_id=slot.id).exists():
                raise ValidationError(
                    "This time slot is already booked for this doctor."
                ) from exc
            if Appointment.objects.active().filter(
                patient_id=patient.pk,
                doctor_id=slot.doctor_id,
                slot__date=slot.date,
            ).exists():
                raise ValidationError(
                    "You already have an active appointment with this doctor on this day."
                ) from exc
            raise ValidationError(
                "You already have another active appointment that overlaps with this time."
            ) from exc

    return appointment
