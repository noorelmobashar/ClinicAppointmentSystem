from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


INACTIVE_APPOINTMENT_STATUSES = ("CANCELLED", "COMPLETED")


class AppointmentQuerySet(models.QuerySet):
    def active(self):
        return self.exclude(status__in=INACTIVE_APPOINTMENT_STATUSES)


class DoctorSchedule(models.Model):
    class DayOfWeek(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="doctor_schedules",
    )
    schedule_date = models.DateField(null=True, blank=True)
    day_of_week = models.PositiveSmallIntegerField(choices=DayOfWeek.choices, null=True, blank=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_duration_minutes = models.PositiveSmallIntegerField()

    def save(self, *args, **kwargs):
        if self.schedule_date:
            self.day_of_week = self.schedule_date.weekday()
        super().save(*args, **kwargs)

    def __str__(self):
        if self.schedule_date:
            return f"{self.doctor} - {self.schedule_date} ({self.get_day_of_week_display()})"
        return f"{self.doctor} - {self.get_day_of_week_display()}"


class AppointmentSlot(models.Model):
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="appointment_slots",
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_booked = models.BooleanField(default=False)

    class Meta:
        unique_together = ['doctor', 'date', 'start_time']

    def __str__(self):
        return f"{self.doctor} - {self.date} {self.start_time}"

class Appointment(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Requested"
        AWAITING_PAYMENT = "AWAITING_PAYMENT", "Awaiting payment"
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELLED = "CANCELLED", "Cancelled"
        CHECKED_IN = "CHECKED_IN", "Checked in"
        COMPLETED = "COMPLETED", "Completed"

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="appointments",
    )

    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="doctor_appointments",
    )

    slot = models.ForeignKey(
        AppointmentSlot,
        on_delete=models.CASCADE,
        related_name="appointments",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    active_slot = models.ForeignKey(
        AppointmentSlot,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        editable=False,
        related_name="active_appointments_guard",
    )
    active_patient_doctor_day = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        editable=False,
    )
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cancelled_appointments",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(null=True, blank=True)
    cancellation_failed = models.IntegerField(default=0)

    objects = AppointmentQuerySet.as_manager()

    INACTIVE_STATUSES = INACTIVE_APPOINTMENT_STATUSES

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["active_slot"],
                name="uniq_active_appointment_per_slot",
            ),
            models.UniqueConstraint(
                fields=["active_patient_doctor_day"],
                name="uniq_active_patient_doctor_day",
            ),
        ]

    @classmethod
    def is_active_status(cls, status):
        return status not in cls.INACTIVE_STATUSES

    def clean(self):
        super().clean()

        if not self.slot_id or not self.patient_id:
            return

        if self.doctor_id and self.doctor_id != self.slot.doctor_id:
            raise ValidationError({
                "doctor": "The selected doctor must match the selected appointment slot.",
            })

        if not self.is_active_status(self.status):
            return

        conflicts = Appointment.objects.active()
        if self.pk:
            conflicts = conflicts.exclude(pk=self.pk)

        if conflicts.filter(slot_id=self.slot_id).exists():
            raise ValidationError(
                "This time slot is already booked for this doctor."
            )

        if conflicts.filter(
            patient_id=self.patient_id,
            doctor_id=self.slot.doctor_id,
            slot__date=self.slot.date,
        ).exists():
            raise ValidationError(
                "You already have an active appointment with this doctor on this day."
            )

        overlapping = conflicts.filter(
            patient_id=self.patient_id,
            slot__date=self.slot.date,
        ).filter(
            Q(slot__start_time__lt=self.slot.end_time)
            & Q(slot__end_time__gt=self.slot.start_time)
        )

        if overlapping.exists():
            raise ValidationError(
                "You already have another active appointment that overlaps with this time."
            )

    def save(self, *args, **kwargs):
        if self.slot_id:
            self.doctor_id = self.slot.doctor_id

        self.active_slot_id = self.slot_id if self.is_active_status(self.status) else None
        if self.slot_id and self.patient_id and self.is_active_status(self.status):
            self.active_patient_doctor_day = (
                f"{self.patient_id}:{self.slot.doctor_id}:{self.slot.date.isoformat()}"
            )
        else:
            self.active_patient_doctor_day = None
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.update({"doctor", "active_slot", "active_patient_doctor_day"})
            kwargs["update_fields"] = list(update_fields)
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.patient} - {self.slot}"


class DoctorException(models.Model):
    class ExceptionType(models.TextChoices):
        VACATION = "VACATION", "Vacation / Day Off"
        WORKING_DAY = "WORKING_DAY", "One-off Working Day"

    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="doctor_exceptions",
    )
    date = models.DateField()
    exception_type = models.CharField(max_length=20, choices=ExceptionType.choices)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    slot_duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.doctor} - {self.date} - {self.get_exception_type_display()}"


class RescheduleHistory(models.Model):
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="reschedule_history",
    )
    old_slot = models.ForeignKey(
        AppointmentSlot,
        on_delete=models.SET_NULL,
        null=True,
        related_name="old_reschedules",
    )
    new_slot = models.ForeignKey(
        AppointmentSlot,
        on_delete=models.SET_NULL,
        null=True,
        related_name="new_reschedules",
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reschedule for {self.appointment.id} at {self.created_at}"



