from django import forms
from .models import Property


class PropertyCreationForm(forms.ModelForm):
    """Form for landlords to create new property listings"""

    # Add image URL fields for now (simple solution)
    image_url_1 = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://example.com/image1.jpg'
        }),
        label='Photo URL 1'
    )
    image_url_2 = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://example.com/image2.jpg'
        }),
        label='Photo URL 2'
    )
    image_url_3 = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://example.com/image3.jpg'
        }),
        label='Photo URL 3'
    )

    class Meta:
        model = Property
        fields = [
            # Basic Information
            'title', 'description', 'property_type',
            # Location Details
            'address', 'suburb', 'state', 'postcode',
            # Property Specifications
            'bedrooms', 'bathrooms', 'car_spaces',
            # Financial Information
            'rent_per_week', 'bond_amount',
            # Availability
            'available_from', 'min_lease_term',
            # Property Features
            'furnished', 'pets_allowed', 'smoking_allowed',
            # Room Information
            'rooms_available', 'max_occupants',
        ]

        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Spacious 2BR apartment in Carlton'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe your property, its features, and location benefits...'
            }),
            'property_type': forms.Select(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '123 Example Street'
            }),
            'suburb': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Carlton'
            }),
            'state': forms.Select(attrs={'class': 'form-control'}),
            'postcode': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '3000'
            }),
            'bedrooms': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 20
            }),
            'bathrooms': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 10
            }),
            'car_spaces': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'max': 10
            }),
            'rent_per_week': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': '350.00'
            }),
            'bond_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': '1400.00'
            }),
            'available_from': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'min_lease_term': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 60,
                'value': 12
            }),
            'furnished': forms.Select(attrs={'class': 'form-control'}),
            'pets_allowed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'smoking_allowed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'rooms_available': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 10,
                'value': 1
            }),
            'max_occupants': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 20
            }),
        }

        labels = {
            'title': 'Property Title',
            'description': 'Property Description',
            'property_type': 'Property Type',
            'rent_per_week': 'Weekly Rent ($)',
            'bond_amount': 'Bond Amount ($)',
            'available_from': 'Available From',
            'min_lease_term': 'Minimum Lease Term (months)',
            'pets_allowed': 'Pets Allowed',
            'smoking_allowed': 'Smoking Allowed',
            'rooms_available': 'Rooms Available for Rent',
            'max_occupants': 'Maximum Total Occupants',
        }