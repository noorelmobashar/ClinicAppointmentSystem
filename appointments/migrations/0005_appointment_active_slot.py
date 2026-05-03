from django.db import migrations, models
import django.db.models.deletion


def backfill_active_slot(apps, schema_editor):
    Appointment = apps.get_model("appointments", "Appointment")

    inactive_statuses = {"CANCELLED", "COMPLETED"}
    kept_active_slots = set()

    for appointment in Appointment.objects.order_by("slot_id", "created_at", "id"):
        if appointment.status in inactive_statuses:
            appointment.active_slot_id = None
            appointment.save(update_fields=["active_slot"])
            continue

        if appointment.slot_id in kept_active_slots:
            appointment.status = "CANCELLED"
            appointment.active_slot_id = None
            appointment.save(update_fields=["status", "active_slot"])
            continue

        appointment.active_slot_id = appointment.slot_id
        appointment.save(update_fields=["active_slot"])
        kept_active_slots.add(appointment.slot_id)


def reverse_backfill_active_slot(apps, schema_editor):
    Appointment = apps.get_model("appointments", "Appointment")
    Appointment.objects.update(active_slot_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ("appointments", "0004_doctorexception_reschedulehistory"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="active_slot",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="active_appointments_guard",
                to="appointments.appointmentslot",
            ),
        ),
        migrations.RunPython(backfill_active_slot, reverse_backfill_active_slot),
        migrations.AddConstraint(
            model_name="appointment",
            constraint=models.UniqueConstraint(
                fields=("active_slot",),
                name="uniq_active_appointment_per_slot",
            ),
        ),
    ]
