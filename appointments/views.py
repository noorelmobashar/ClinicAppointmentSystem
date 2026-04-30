from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.timezone import now

from .models import Appointment, AppointmentSlot


@login_required
def available_slots(request):
    doctor_id = request.GET.get("doctor")
    date = request.GET.get("date")

    slots = AppointmentSlot.objects.filter(
        doctor_id=doctor_id,
        date=date,
        is_booked=False,
    ).order_by("start_time")

    data = []
    for slot in slots:
        data.append({
            "id": slot.id,
            "time": slot.start_time.strftime("%H:%M"),
        })

    return JsonResponse(data, safe=False)


@login_required
def patient_booking(request):
    User = get_user_model()
    doctors = User.objects.filter(role="DOCTOR").select_related("doctor_profile").order_by("first_name", "username")

    return render(request, "patients/booking_wizard.html", {
        "doctors": doctors,
        "current_section": "book",
        "dashboard_title": "Book a new appointment",
        "dashboard_subtitle": "Choose a doctor, review availability, and confirm the next clinic visit.",
    })


@transaction.atomic
@login_required
def book_appointment(request, slot_id):
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    slot = AppointmentSlot.objects.select_for_update().get(id=slot_id)

    if slot.is_booked:
        return HttpResponse("Already booked")

    exists = Appointment.objects.filter(
        patient=request.user,
        slot__date=slot.date,
        slot__start_time=slot.start_time,
    ).exists()

    if exists:
        return HttpResponse("You already booked this time")

    Appointment.objects.create(
        patient=request.user,
        doctor=slot.doctor,
        slot=slot,
        status=Appointment.Status.AWAITING_PAYMENT,
    )

    slot.is_booked = True
    slot.save()

    return HttpResponse("Booked successfully")


@login_required
def patient_history(request):
    upcoming = Appointment.objects.filter(
        patient=request.user,
        slot__date__gte=now().date(),
    ).select_related("doctor", "slot").order_by("slot__date", "slot__start_time")

    history = Appointment.objects.filter(
        patient=request.user,
        slot__date__lt=now().date(),
    ).select_related("doctor", "slot").order_by("-slot__date", "-slot__start_time")

    return render(request, "patients/my_appointments.html", {
        "upcoming": upcoming,
        "history": history,
        "current_section": "appointments",
        "dashboard_title": "My appointments",
        "dashboard_subtitle": "Review upcoming visits, booking history, and the current status of each appointment.",
    })
