from django.http import JsonResponse, HttpResponse
from django.db import transaction
from .models import AppointmentSlot, Appointment
from django.utils.timezone import now



def available_slots(request):
    doctor_id = request.GET.get("doctor")
    date = request.GET.get("date")

    slots = AppointmentSlot.objects.filter(
        doctor_id=doctor_id,
        date=date,
        is_booked=False
    )

    data = []
    for slot in slots:
        data.append({
            "id": slot.id,
            "time": slot.start_time.strftime("%H:%M"),
        })

    return JsonResponse(data, safe=False)



@transaction.atomic
def book_appointment(request, slot_id):

    slot = AppointmentSlot.objects.select_for_update().get(id=slot_id)


    if slot.is_booked:
        return HttpResponse("Already booked")


    exists = Appointment.objects.filter(
        patient=request.user,
        slot__date=slot.date,
        slot__start_time=slot.start_time
    ).exists()

    if exists:
        return HttpResponse("You already booked this time")


    Appointment.objects.create(
        patient=request.user,
        doctor=slot.doctor,
        slot=slot,
        status="AWAITING_PAYMENT"
    )


    slot.is_booked = True
    slot.save()

    return HttpResponse("Booked successfully")

def patient_history(request):
    upcoming = Appointment.objects.filter(
        patient=request.user,
        slot__date__gte=now().date()
    )

    history = Appointment.objects.filter(
        patient=request.user,
        slot__date__lt=now().date()
    )

    return render(request, "patients/my_appointments.html", {
        "upcoming": upcoming,
        "history": history
    })