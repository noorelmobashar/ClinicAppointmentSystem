from django.db import migrations, models


def backfill_active_patient_doctor_day(apps, schema_editor):
    Appointment = apps.get_model("appointments", "Appointment")

    inactive_statuses = {"CANCELLED", "COMPLETED"}
    kept_keys = set()

    for appointment in Appointment.objects.select_related("slot").order_by(
        "patient_id",
        "doctor_id",
        "slot__date",
        "created_at",
        "id",
    ):
        if appointment.status in inactive_statuses or appointment.slot_id is None:
            appointment.active_patient_doctor_day = None
            appointment.save(update_fields=["active_patient_doctor_day"])
            continue

        key = f"{appointment.patient_id}:{appointment.doctor_id}:{appointment.slot.date.isoformat()}"
        if key in kept_keys:
            appointment.status = "CANCELLED"
            appointment.active_slot_id = None
            appointment.active_patient_doctor_day = None
            appointment.save(
                update_fields=["status", "active_slot", "active_patient_doctor_day"]
            )
            continue

        appointment.active_patient_doctor_day = key
        appointment.save(update_fields=["active_patient_doctor_day"])
        kept_keys.add(key)


def reverse_backfill_active_patient_doctor_day(apps, schema_editor):
    Appointment = apps.get_model("appointments", "Appointment")
    Appointment.objects.update(active_patient_doctor_day=None)


class Migration(migrations.Migration):

    dependencies = [
        ("appointments", "0005_appointment_active_slot"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="active_patient_doctor_day",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=128,
                null=True,
            ),
        ),
        migrations.RunPython(
            backfill_active_patient_doctor_day,
            reverse_backfill_active_patient_doctor_day,
        ),
        migrations.AddConstraint(
            model_name="appointment",
            constraint=models.UniqueConstraint(
                fields=("active_patient_doctor_day",),
                name="uniq_active_patient_doctor_day",
            ),
        ),
    ]
