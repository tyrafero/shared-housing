from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse
from .models import UserProfile
from .forms import (
    PersonalInfoForm, LocationPreferencesForm, BudgetHousingForm,
    LifestyleForm, RoommatePreferencesForm, AboutYourselfForm
)


@login_required
def profile_setup(request):
    """Main profile setup view - redirects to appropriate step"""
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    # Determine which step to show based on profile completion
    step = request.GET.get('step', profile_get_current_step(profile))

    # Redirect to specific step
    return redirect('profiles:setup_step', step=step)


@login_required
def profile_setup_step(request, step):
    """Handle individual steps of profile setup"""
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    # Validate step
    valid_steps = ['personal', 'location', 'budget', 'lifestyle', 'roommates', 'about']
    if step not in valid_steps:
        messages.error(request, 'Invalid profile setup step.')
        return redirect('profiles:setup')

    # Get form class for this step
    form_classes = {
        'personal': PersonalInfoForm,
        'location': LocationPreferencesForm,
        'budget': BudgetHousingForm,
        'lifestyle': LifestyleForm,
        'roommates': RoommatePreferencesForm,
        'about': AboutYourselfForm,
    }

    form_class = form_classes[step]
    step_titles = {
        'personal': 'Personal Information',
        'location': 'Location Preferences',
        'budget': 'Budget & Housing',
        'lifestyle': 'Lifestyle & Habits',
        'roommates': 'Roommate Preferences',
        'about': 'About Yourself',
    }

    if request.method == 'POST':
        form = form_class(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()

            # Update user's profile step
            current_step_index = valid_steps.index(step)
            if request.user.profile_step <= current_step_index + 1:
                request.user.profile_step = min(current_step_index + 2, len(valid_steps) + 1)
                request.user.save(update_fields=['profile_step'])

            # Check if this is the last step
            if step == 'about':
                # Mark profile as completed if it meets requirements
                if profile.is_complete:
                    request.user.profile_completed = True
                    request.user.save(update_fields=['profile_completed'])
                    messages.success(request, 'Profile completed successfully! You can now start finding roommates.')
                    return redirect('core:dashboard')
                else:
                    messages.warning(request, 'Profile saved, but some required fields are missing.')

            # Redirect to next step
            next_step_index = current_step_index + 1
            if next_step_index < len(valid_steps):
                next_step = valid_steps[next_step_index]
                messages.success(request, f'Step {current_step_index + 1} completed!')
                return redirect('profiles:setup_step', step=next_step)
            else:
                return redirect('core:dashboard')
    else:
        form = form_class(instance=profile)

    # Context for template
    context = {
        'form': form,
        'step': step,
        'step_title': step_titles[step],
        'step_number': valid_steps.index(step) + 1,
        'total_steps': len(valid_steps),
        'progress_percentage': ((valid_steps.index(step) + 1) / len(valid_steps)) * 100,
        'profile': profile,
        'valid_steps': valid_steps,
    }

    return render(request, 'profiles/setup_step.html', context)


@login_required
def profile_view(request, user_id=None):
    """View user profile"""
    if user_id:
        # Viewing someone else's profile
        profile = get_object_or_404(UserProfile, user__id=user_id, user__is_active=True)
        # Increment profile views
        if profile.user != request.user:
            profile.profile_views += 1
            profile.save(update_fields=['profile_views'])
    else:
        # Viewing own profile
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        if created or not profile.is_complete:
            return redirect('profiles:setup')

    context = {
        'profile': profile,
        'is_own_profile': profile.user == request.user,
        'can_message': profile.user != request.user and request.user.is_authenticated,
    }

    return render(request, 'profiles/profile_view.html', context)


@login_required
def profile_edit(request):
    """Edit existing profile"""
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if created:
        return redirect('profiles:setup')

    # Handle specific section editing
    section = request.GET.get('section', 'personal')
    valid_sections = ['personal', 'location', 'budget', 'lifestyle', 'roommates', 'about']

    if section not in valid_sections:
        section = 'personal'

    # Map sections to forms (same as setup)
    form_classes = {
        'personal': PersonalInfoForm,
        'location': LocationPreferencesForm,
        'budget': BudgetHousingForm,
        'lifestyle': LifestyleForm,
        'roommates': RoommatePreferencesForm,
        'about': AboutYourselfForm,
    }

    form_class = form_classes[section]

    if request.method == 'POST':
        form = form_class(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, f'{section.title()} section updated successfully!')
            return redirect('profiles:profile_edit')
    else:
        form = form_class(instance=profile)

    context = {
        'form': form,
        'section': section,
        'valid_sections': valid_sections,
        'profile': profile,
    }

    return render(request, 'profiles/profile_edit.html', context)


def profile_get_current_step(profile):
    """Determine the current step based on profile completion"""
    if not profile.date_of_birth or not profile.occupation:
        return 'personal'
    if not profile.preferred_locations and not profile.max_commute_time:
        return 'location'
    if not profile.min_budget or not profile.max_budget:
        return 'budget'
    if profile.cleanliness_level == 5 and profile.noise_tolerance == 5:  # Default values
        return 'lifestyle'
    if not profile.preferred_age_min or not profile.preferred_age_max:
        return 'roommates'
    if not profile.bio:
        return 'about'
    return 'personal'  # Fallback


@login_required
def profile_progress_api(request):
    """API endpoint to get profile completion progress"""
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    return JsonResponse({
        'completion_percentage': profile.completion_percentage,
        'is_complete': profile.is_complete,
        'current_step': profile_get_current_step(profile),
    })


@login_required
def profile_skip_step(request, step):
    """Allow users to skip optional steps"""
    if request.method == 'POST':
        valid_steps = ['personal', 'location', 'budget', 'lifestyle', 'roommates', 'about']

        if step not in valid_steps:
            messages.error(request, 'Invalid step.')
            return redirect('profiles:setup')

        # Update user's profile step
        current_step_index = valid_steps.index(step)
        if request.user.profile_step <= current_step_index + 1:
            request.user.profile_step = min(current_step_index + 2, len(valid_steps) + 1)
            request.user.save(update_fields=['profile_step'])

        # Redirect to next step or dashboard
        next_step_index = current_step_index + 1
        if next_step_index < len(valid_steps):
            next_step = valid_steps[next_step_index]
            messages.info(request, f'Step skipped. You can always complete it later.')
            return redirect('profiles:setup_step', step=next_step)
        else:
            return redirect('core:dashboard')

    return redirect('profiles:setup')