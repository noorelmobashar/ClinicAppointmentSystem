from datetime import datetime, timedelta

from django.utils import timezone

from .models import AppointmentSlot, DoctorSchedule


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
