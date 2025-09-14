from django import forms
from django.contrib.auth import get_user_model
from .models import RoommateGroup, PropertyApplication

User = get_user_model()


class CreateGroupForm(forms.ModelForm):
    """Form for creating a new roommate group"""

    class Meta:
        model = RoommateGroup
        fields = [
            'name', 'description', 'max_members', 'min_members',
            'target_budget_min', 'target_budget_max',
            'preferred_locations', 'required_bedrooms', 'required_bathrooms',
            'move_in_date', 'lease_length_months',
            'pet_friendly', 'smoking_allowed', 'furnished_preference',
            'is_private'
        ]

        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter group name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe your group, goals, and what you\'re looking for...'
            }),
            'max_members': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 2,
                'max': 10
            }),
            'min_members': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 2,
                'max': 8
            }),
            'target_budget_min': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Minimum total weekly rent'
            }),
            'target_budget_max': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Maximum total weekly rent'
            }),
            'required_bedrooms': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 10
            }),
            'required_bathrooms': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 5
            }),
            'move_in_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'lease_length_months': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 24,
                'placeholder': 'Lease length in months'
            }),
            'pet_friendly': forms.Select(choices=[
                ('', 'No preference'),
                (True, 'Must be pet-friendly'),
                (False, 'No pets')
            ], attrs={'class': 'form-control'}),
            'smoking_allowed': forms.Select(choices=[
                ('', 'No preference'),
                (True, 'Smoking allowed'),
                (False, 'No smoking')
            ], attrs={'class': 'form-control'}),
            'furnished_preference': forms.Select(attrs={'class': 'form-control'}),
            'is_private': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set up preferred_locations as a text field for now
        self.fields['preferred_locations'] = forms.CharField(
            required=False,
            widget=forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter preferred suburbs/areas separated by commas'
            }),
            help_text='Enter preferred locations separated by commas (e.g., Sydney CBD, Bondi, Paddington)'
        )

    def clean_preferred_locations(self):
        """Convert comma-separated locations to list"""
        locations = self.cleaned_data.get('preferred_locations', '')
        if locations:
            return [loc.strip() for loc in locations.split(',') if loc.strip()]
        return []

    def clean(self):
        cleaned_data = super().clean()
        min_members = cleaned_data.get('min_members')
        max_members = cleaned_data.get('max_members')

        if min_members and max_members and min_members > max_members:
            raise forms.ValidationError(
                "Minimum members cannot be greater than maximum members."
            )

        budget_min = cleaned_data.get('target_budget_min')
        budget_max = cleaned_data.get('target_budget_max')

        if budget_min and budget_max and budget_min > budget_max:
            raise forms.ValidationError(
                "Minimum budget cannot be greater than maximum budget."
            )

        return cleaned_data


class EditGroupForm(forms.ModelForm):
    """Form for editing an existing roommate group"""

    class Meta:
        model = RoommateGroup
        fields = [
            'name', 'description', 'status',
            'target_budget_min', 'target_budget_max',
            'preferred_locations', 'required_bedrooms', 'required_bathrooms',
            'move_in_date', 'lease_length_months',
            'pet_friendly', 'smoking_allowed', 'furnished_preference'
        ]

        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'target_budget_min': forms.NumberInput(attrs={'class': 'form-control'}),
            'target_budget_max': forms.NumberInput(attrs={'class': 'form-control'}),
            'required_bedrooms': forms.NumberInput(attrs={'class': 'form-control'}),
            'required_bathrooms': forms.NumberInput(attrs={'class': 'form-control'}),
            'move_in_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'lease_length_months': forms.NumberInput(attrs={'class': 'form-control'}),
            'pet_friendly': forms.Select(choices=[
                ('', 'No preference'),
                (True, 'Must be pet-friendly'),
                (False, 'No pets')
            ], attrs={'class': 'form-control'}),
            'smoking_allowed': forms.Select(choices=[
                ('', 'No preference'),
                (True, 'Smoking allowed'),
                (False, 'No smoking')
            ], attrs={'class': 'form-control'}),
            'furnished_preference': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set up preferred_locations display
        if self.instance and self.instance.preferred_locations:
            locations_str = ', '.join(self.instance.preferred_locations)
        else:
            locations_str = ''

        self.fields['preferred_locations'] = forms.CharField(
            required=False,
            initial=locations_str,
            widget=forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter preferred suburbs/areas separated by commas'
            })
        )

    def clean_preferred_locations(self):
        """Convert comma-separated locations to list"""
        locations = self.cleaned_data.get('preferred_locations', '')
        if locations:
            return [loc.strip() for loc in locations.split(',') if loc.strip()]
        return []


class JoinGroupForm(forms.Form):
    """Form for requesting to join a group"""

    join_reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Tell the group why you would like to join and what you can bring...'
        }),
        help_text='This message will be visible to group admins when reviewing your request.'
    )


class InviteMembersForm(forms.Form):
    """Form for inviting members to a group"""

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter email address'
        })
    )

    message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional personal message...'
        })
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        try:
            user = User.objects.get(email=email, is_active=True)
            return user
        except User.DoesNotExist:
            raise forms.ValidationError("No active user found with this email address.")


class PropertyApplicationForm(forms.ModelForm):
    """Form for applying to properties as a group"""

    class Meta:
        model = PropertyApplication
        fields = [
            'application_message',
            'proposed_move_in_date',
            'proposed_lease_length'
        ]

        widgets = {
            'application_message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Introduce your group to the property owner/agent. Mention your group size, employment status, references, and why you would be good tenants...'
            }),
            'proposed_move_in_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'proposed_lease_length': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 24,
                'placeholder': 'Lease length in months'
            })
        }

    def clean_application_message(self):
        message = self.cleaned_data.get('application_message', '').strip()
        if len(message) < 50:
            raise forms.ValidationError(
                "Application message must be at least 50 characters long."
            )
        return message


class VoteForm(forms.Form):
    """Form for voting on property applications"""

    VOTE_CHOICES = [
        ('yes', 'Yes - I support this application'),
        ('no', 'No - I do not support this application'),
        ('abstain', 'Abstain - I have no preference'),
    ]

    vote = forms.ChoiceField(
        choices=VOTE_CHOICES,
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input'
        })
    )

    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional comment about your vote...'
        })
    )