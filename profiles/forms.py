from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import UserProfile
import json


class PersonalInfoForm(forms.ModelForm):
    """Step 1: Basic personal information"""

    class Meta:
        model = UserProfile
        fields = ['date_of_birth', 'gender', 'occupation', 'education_level']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'max': timezone.now().date().strftime('%Y-%m-%d')
            }),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'occupation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Software Developer, Student, Teacher'
            }),
            'education_level': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            age = timezone.now().date().year - dob.year
            if age < 18:
                raise ValidationError("You must be at least 18 years old.")
            if age > 99:
                raise ValidationError("Please enter a valid date of birth.")
        return dob


class LocationPreferencesForm(forms.ModelForm):
    """Step 2: Location and transport preferences"""

    preferred_locations_input = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Darlinghurst, Newtown, Kings Cross (comma-separated)'
        }),
        help_text="Enter preferred suburbs/areas separated by commas"
    )

    class Meta:
        model = UserProfile
        fields = ['max_commute_time', 'has_car']
        widgets = {
            'max_commute_time': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '5',
                'max': '120',
                'placeholder': '30'
            }),
            'has_car': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.preferred_locations and isinstance(self.instance.preferred_locations, list):
            self.fields['preferred_locations_input'].initial = ', '.join(self.instance.preferred_locations)

    def clean_preferred_locations_input(self):
        locations_str = self.cleaned_data.get('preferred_locations_input', '')
        if locations_str and isinstance(locations_str, str):
            locations = [loc.strip() for loc in locations_str.split(',') if loc.strip()]
            if len(locations) > 10:
                raise ValidationError("Please select no more than 10 preferred locations.")
            return locations
        return []

    def save(self, commit=True):
        instance = super().save(commit=False)
        # The cleaned data is already processed by clean_preferred_locations_input
        locations = self.cleaned_data.get('preferred_locations_input', [])
        instance.preferred_locations = locations if isinstance(locations, list) else []
        if commit:
            instance.save()
        return instance


class BudgetHousingForm(forms.ModelForm):
    """Step 3: Budget and housing preferences"""

    class Meta:
        model = UserProfile
        fields = [
            'min_budget', 'max_budget', 'preferred_room_type',
            'lease_duration', 'move_in_date'
        ]
        widgets = {
            'min_budget': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '50',
                'step': '50',
                'placeholder': '200'
            }),
            'max_budget': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '50',
                'step': '50',
                'placeholder': '400'
            }),
            'preferred_room_type': forms.Select(attrs={'class': 'form-select'}),
            'lease_duration': forms.Select(attrs={'class': 'form-select'}),
            'move_in_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'min': timezone.now().date().strftime('%Y-%m-%d')
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        min_budget = cleaned_data.get('min_budget')
        max_budget = cleaned_data.get('max_budget')

        if min_budget and max_budget:
            if min_budget >= max_budget:
                raise ValidationError("Minimum budget must be less than maximum budget.")
            if max_budget - min_budget < 50:
                raise ValidationError("Budget range should be at least $50.")

        return cleaned_data


class LifestyleForm(forms.ModelForm):
    """Step 4: Lifestyle preferences and habits"""

    class Meta:
        model = UserProfile
        fields = [
            'cleanliness_level', 'noise_tolerance', 'social_level',
            'smoker', 'drinking', 'pets', 'schedule_type', 'works_from_home'
        ]
        widgets = {
            'cleanliness_level': forms.NumberInput(attrs={
                'type': 'range',
                'class': 'form-range',
                'min': '1',
                'max': '10',
                'step': '1',
                'oninput': 'this.nextElementSibling.value=this.value'
            }),
            'noise_tolerance': forms.NumberInput(attrs={
                'type': 'range',
                'class': 'form-range',
                'min': '1',
                'max': '10',
                'step': '1',
                'oninput': 'this.nextElementSibling.value=this.value'
            }),
            'social_level': forms.NumberInput(attrs={
                'type': 'range',
                'class': 'form-range',
                'min': '1',
                'max': '10',
                'step': '1',
                'oninput': 'this.nextElementSibling.value=this.value'
            }),
            'smoker': forms.Select(attrs={'class': 'form-select'}),
            'drinking': forms.Select(attrs={'class': 'form-select'}),
            'pets': forms.Select(attrs={'class': 'form-select'}),
            'schedule_type': forms.Select(attrs={'class': 'form-select'}),
            'works_from_home': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class RoommatePreferencesForm(forms.ModelForm):
    """Step 5: Roommate preferences"""

    class Meta:
        model = UserProfile
        fields = [
            'preferred_age_min', 'preferred_age_max',
            'preferred_gender', 'max_roommates'
        ]
        widgets = {
            'preferred_age_min': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '18',
                'max': '99',
                'placeholder': '20'
            }),
            'preferred_age_max': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '18',
                'max': '99',
                'placeholder': '35'
            }),
            'preferred_gender': forms.Select(attrs={'class': 'form-select'}),
            'max_roommates': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '10',
                'placeholder': '3'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        min_age = cleaned_data.get('preferred_age_min')
        max_age = cleaned_data.get('preferred_age_max')

        if min_age and max_age:
            if min_age >= max_age:
                raise ValidationError("Minimum age must be less than maximum age.")

        return cleaned_data


class AboutYourselfForm(forms.ModelForm):
    """Step 6: Bio, interests, and additional info"""

    interests_input = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Reading, Cooking, Hiking, Music (comma-separated)'
        }),
        help_text="Enter your interests/hobbies separated by commas"
    )

    languages_input = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., English, Spanish, Mandarin (comma-separated)'
        }),
        help_text="Enter languages you speak separated by commas"
    )

    class Meta:
        model = UserProfile
        fields = ['bio', 'profile_picture']
        widgets = {
            'bio': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'maxlength': '1000',
                'placeholder': 'Tell others about yourself, your lifestyle, what you\'re looking for in a roommate...'
            }),
            'profile_picture': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance:
            if self.instance.interests and isinstance(self.instance.interests, list):
                self.fields['interests_input'].initial = ', '.join(self.instance.interests)
            if self.instance.languages and isinstance(self.instance.languages, list):
                self.fields['languages_input'].initial = ', '.join(self.instance.languages)

    def clean_interests_input(self):
        interests_str = self.cleaned_data.get('interests_input', '')
        if interests_str and isinstance(interests_str, str):
            interests = [interest.strip() for interest in interests_str.split(',') if interest.strip()]
            if len(interests) > 20:
                raise ValidationError("Please select no more than 20 interests.")
            return interests
        return []

    def clean_languages_input(self):
        languages_str = self.cleaned_data.get('languages_input', '')
        if languages_str and isinstance(languages_str, str):
            languages = [lang.strip() for lang in languages_str.split(',') if lang.strip()]
            if len(languages) > 10:
                raise ValidationError("Please select no more than 10 languages.")
            return languages
        return []

    def save(self, commit=True):
        instance = super().save(commit=False)

        # The cleaned data is already processed by the clean methods
        interests = self.cleaned_data.get('interests_input', [])
        languages = self.cleaned_data.get('languages_input', [])

        instance.interests = interests if isinstance(interests, list) else []
        instance.languages = languages if isinstance(languages, list) else []

        if commit:
            instance.save()
        return instance