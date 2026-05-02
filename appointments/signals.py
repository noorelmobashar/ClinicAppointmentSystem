from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import DoctorSchedule
from .services import rebuild_doctor_weekday_slots, sync_schedule_slots


@receiver(post_save, sender=DoctorSchedule)
def generate_schedule_slots(sender, instance, **kwargs):
    sync_schedule_slots(instance)


@receiver(post_delete, sender=DoctorSchedule)
def delete_schedule_slots(sender, instance, **kwargs):
    rebuild_doctor_weekday_slots(
        doctor=instance.doctor,
        weekday=instance.day_of_week,
    )
