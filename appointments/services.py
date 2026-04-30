from datetime import datetime, timedelta
from .models import AppointmentSlot


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