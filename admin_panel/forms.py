from django import forms
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from accounts.models import CustomUser, DoctorProfile, PatientProfile

class AdminUserCreateForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, validators=[validate_password])
    
    # Doctor Fields
    specialty = forms.CharField(max_length=100, required=False)
    bio = forms.CharField(widget=forms.Textarea, required=False)
    consultation_fee = forms.DecimalField(max_digits=8, decimal_places=2, required=False, initial=0)
    
    # Patient Fields
    date_of_birth = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False, initial=timezone.now().date)
    blood_type = forms.CharField(max_length=5, required=False)
    
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'phone_number', 'role', 'password']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.is_active = True
        if commit:
            user.save()
            self._save_profile(user)
        return user

    def _save_profile(self, user):
        if user.role == 'DOCTOR':
            DoctorProfile.objects.update_or_create(
                user=user,
                defaults={
                    'specialty': self.cleaned_data.get('specialty', ''),
                    'bio': self.cleaned_data.get('bio', ''),
                    'consultation_fee': self.cleaned_data.get('consultation_fee') or 0,
                }
            )
        elif user.role == 'PATIENT':
            PatientProfile.objects.update_or_create(
                user=user,
                defaults={
                    'date_of_birth': self.cleaned_data.get('date_of_birth') or timezone.now().date(),
                    'blood_type': self.cleaned_data.get('blood_type', ''),
                }
            )


class AdminUserEditForm(forms.ModelForm):
    # Doctor Fields
    specialty = forms.CharField(max_length=100, required=False)
    bio = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    consultation_fee = forms.DecimalField(max_digits=8, decimal_places=2, required=False)
    
    # Patient Fields
    date_of_birth = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), required=False)
    blood_type = forms.CharField(max_length=5, required=False)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'phone_number', 'role', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if hasattr(self.instance, 'doctor_profile'):
                self.fields['specialty'].initial = self.instance.doctor_profile.specialty
                self.fields['bio'].initial = self.instance.doctor_profile.bio
                self.fields['consultation_fee'].initial = self.instance.doctor_profile.consultation_fee
            if hasattr(self.instance, 'patient_profile'):
                self.fields['date_of_birth'].initial = self.instance.patient_profile.date_of_birth
                self.fields['blood_type'].initial = self.instance.patient_profile.blood_type

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            self._save_profile(user)
        return user

    def _save_profile(self, user):
        if user.role == 'DOCTOR':
            DoctorProfile.objects.update_or_create(
                user=user,
                defaults={
                    'specialty': self.cleaned_data.get('specialty') or '',
                    'bio': self.cleaned_data.get('bio') or '',
                    'consultation_fee': self.cleaned_data.get('consultation_fee') or 0,
                }
            )
        elif user.role == 'PATIENT':
            PatientProfile.objects.update_or_create(
                user=user,
                defaults={
                    'date_of_birth': self.cleaned_data.get('date_of_birth') or timezone.now().date(),
                    'blood_type': self.cleaned_data.get('blood_type') or '',
                }
            )
