from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import reverse
from .forms import CustomUserCreationForm, CustomAuthenticationForm, EmailVerificationForm, LandlordRegistrationForm
from .models import CustomUser
from .tokens import account_activation_token


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = True  # User can login but needs email verification
            user.save()

            # Send verification email
            send_verification_email(request, user)

            messages.success(
                request,
                'Registration successful! Please check your email to verify your account.'
            )
            return redirect('accounts:login')
    else:
        form = CustomUserCreationForm()

    return render(request, 'accounts/register.html', {'form': form})


def custom_login(request):
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)

                # Redirect based on profile completion (only renters need detailed profile)
                if not user.profile_completed and user.is_renter:
                    return redirect('profiles:setup')

                # Check if user has a next parameter
                next_url = request.GET.get('next')
                if next_url:
                    return HttpResponseRedirect(next_url)

                return redirect('core:dashboard')
    else:
        form = CustomAuthenticationForm()

    return render(request, 'accounts/login.html', {'form': form})


@login_required
def email_verification_sent(request):
    return render(request, 'accounts/email_verification_sent.html')


def verify_email(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = CustomUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
        user = None

    if user is not None and account_activation_token.check_token(user, token):
        user.email_verified = True
        user.save()
        login(request, user)
        messages.success(request, 'Your email has been verified successfully!')

        if not user.profile_completed and user.is_renter:
            return redirect('profiles:setup')
        return redirect('core:dashboard')
    else:
        messages.error(request, 'The verification link is invalid or has expired.')
        return redirect('accounts:login')


@login_required
def resend_verification(request):
    if request.method == 'POST':
        form = EmailVerificationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = CustomUser.objects.get(email=email)
                if user.email_verified:
                    messages.info(request, 'Your email is already verified.')
                else:
                    send_verification_email(request, user)
                    messages.success(request, 'Verification email sent successfully!')
            except CustomUser.DoesNotExist:
                messages.error(request, 'No account found with this email address.')
            return redirect('accounts:email_verification_sent')
    else:
        form = EmailVerificationForm()

    return render(request, 'accounts/resend_verification.html', {'form': form})


def send_verification_email(request, user):
    """Helper function to send verification email"""
    mail_subject = 'Activate your Shared Housing account'
    message = render_to_string('accounts/email_verification.html', {
        'user': user,
        'domain': request.get_host(),
        'uid': urlsafe_base64_encode(force_bytes(user.pk)),
        'token': account_activation_token.make_token(user),
        'protocol': 'https' if request.is_secure() else 'http',
    })

    send_mail(
        mail_subject,
        strip_tags(message),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        html_message=message,
        fail_silently=False,
    )


def landlord_register(request):
    """Separate registration process for landlords"""
    if request.method == 'POST':
        form = LandlordRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = True  # User can login but needs email verification
            user.profile_completed = True  # Landlords don't need detailed profile setup
            user.save()

            # Send verification email
            send_verification_email(request, user)

            messages.success(
                request,
                'Landlord registration successful! Please check your email to verify your account. '
                'You will need to complete identity verification before listing properties.'
            )
            return redirect('accounts:login')
    else:
        form = LandlordRegistrationForm()

    return render(request, 'accounts/landlord_register.html', {'form': form})


def registration_choice(request):
    """Landing page to choose between renter and landlord registration"""
    return render(request, 'accounts/registration_choice.html')


@login_required
def profile_redirect(request):
    """Redirect users based on their profile completion status"""
    if not request.user.profile_completed and request.user.is_renter:
        return redirect('profiles:setup')
    return redirect('core:dashboard')