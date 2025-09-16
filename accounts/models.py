from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from .managers import CustomUserManager


class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    # Profile completion tracking
    profile_completed = models.BooleanField(default=False)
    profile_step = models.IntegerField(default=1)  # Track which step of profile setup

    # Account verification
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)

    # Account status
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(blank=True, null=True)

    # User type
    USER_TYPES = (
        ('renter', 'Renter'),
        ('landlord', 'Landlord'),
        ('admin', 'Administrator'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPES, default='renter')

    # Terms and privacy
    terms_accepted = models.BooleanField(default=False)
    privacy_accepted = models.BooleanField(default=False)
    marketing_consent = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        db_table = 'accounts_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.email

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        return self.first_name

    @property
    def is_verified(self):
        return self.email_verified

    @property
    def is_admin(self):
        return self.user_type == 'admin' or self.is_staff

    @property
    def is_landlord(self):
        return self.user_type == 'landlord'

    @property
    def is_renter(self):
        return self.user_type == 'renter'

    def can_list_properties(self):
        return self.is_landlord or self.is_admin

    def can_access_admin(self):
        return self.is_admin