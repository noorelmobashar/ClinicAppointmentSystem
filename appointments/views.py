from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.timezone import now

from .models import Appointment, AppointmentSlot


@login_required
def available_slots(request):
    doctor_id = request.GET.get("doctor")
    date = request.GET.get("date")
    doctor = None

    if doctor_id:
        doctor = get_user_model().objects.select_related("doctor_profile").filter(
            id=doctor_id,
            role="DOCTOR",
        ).first()

    slots = AppointmentSlot.objects.filter(
        doctor_id=doctor_id,
        date=date,
        is_booked=False,
    ).order_by("start_time")

    # If querying today's slots, exclude ones that have already passed
    current = now()
    if date == current.date().isoformat():
        slots = slots.filter(start_time__gt=current.time())

    data = []
    for slot in slots:
        data.append({
            "id": slot.id,
            "time": slot.start_time.strftime("%H:%M"),
        })

    consultation_fee = getattr(getattr(doctor, "doctor_profile", None), "consultation_fee", 0)

    return JsonResponse({
        "doctor_id": doctor_id,
        "consultation_fee": str(consultation_fee),
        "slots": data,
    })


@login_required
def patient_booking(request):
    User = get_user_model()
    query = (request.GET.get("q") or "").strip()
    specialty = (request.GET.get("specialty") or "").strip()
    selected_doctor_id = (request.GET.get("doctor") or "").strip()

    doctors = User.objects.filter(role="DOCTOR").select_related("doctor_profile")

    if query:
        doctors = doctors.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(username__icontains=query)
            | Q(doctor_profile__specialty__icontains=query)
        )

    if specialty:
        doctors = doctors.filter(doctor_profile__specialty__iexact=specialty)

    doctors = doctors.order_by("first_name", "last_name", "username")
    specialties = (
        User.objects.filter(role="DOCTOR", doctor_profile__specialty__isnull=False)
        .exclude(doctor_profile__specialty__exact="")
        .values_list("doctor_profile__specialty", flat=True)
        .distinct()
        .order_by("doctor_profile__specialty")
    )

    return render(request, "patients/booking_wizard.html", {
        "doctors": doctors,
        "specialties": specialties,
        "search_query": query,
        "selected_specialty": specialty,
        "selected_doctor_id": selected_doctor_id,
        "today": now().date().isoformat(),
        "current_section": "book",
        "dashboard_title": "Book a new appointment",
        "dashboard_subtitle": "Choose a doctor, review availability, and confirm the next clinic visit.",
    })


@login_required
def doctor_profile_detail(request, doctor_id):
    doctor = get_object_or_404(
        get_user_model().objects.select_related("doctor_profile"),
        id=doctor_id,
        role="DOCTOR",
    )
    upcoming_slots = AppointmentSlot.objects.filter(
        doctor=doctor,
        is_booked=False,
        date__gte=now().date(),
    ).order_by("date", "start_time")[:6]

    return render(request, "profile/doctor_public_profile.html", {
        "doctor": doctor,
        "doctor_profile": getattr(doctor, "doctor_profile", None),
        "upcoming_slots": upcoming_slots,
        "current_section": "book",
        "dashboard_title": "Doctor profile",
        "dashboard_subtitle": "Review professional information and continue to booking.",
    })


@login_required
def book_appointment(request, slot_id):
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    slot = AppointmentSlot.objects.get(id=slot_id)

    if slot.is_booked:
        return JsonResponse({"error": "The session is already booked by another user."}, status=400)

    # Reject if the slot date/time has already passed
    from datetime import datetime, timezone as dt_tz
    slot_dt = datetime.combine(slot.date, slot.start_time, tzinfo=dt_tz.utc)
    if slot_dt <= now():
        return JsonResponse({"error": "This time slot has already passed."}, status=400)

    exists = Appointment.objects.filter(
        patient=request.user,
        slot__date=slot.date,
        slot__start_time=slot.start_time,
    ).exists()

    if exists:
        return JsonResponse({"error": "You already booked this time"}, status=400)

    appointment = Appointment.objects.create(
        patient=request.user,
        doctor=slot.doctor,
        slot=slot,
        status=Appointment.Status.AWAITING_PAYMENT,
    )
    consultation_fee = getattr(getattr(slot.doctor, "doctor_profile", None), "consultation_fee", 0)

    # Do not mark slot.is_booked = True yet!
    return JsonResponse({
        "redirect": f"/payments/checkout/{appointment.id}/",
        "consultation_fee": str(consultation_fee),
    })


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
