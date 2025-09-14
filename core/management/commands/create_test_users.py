from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from profiles.models import UserProfile
from datetime import date, timedelta
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Create test users with sample profiles for development'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=5,
            help='Number of test users to create (default: 5)',
        )

    def handle(self, *args, **options):
        count = options['count']

        sample_data = {
            'occupations': ['Software Developer', 'Student', 'Teacher', 'Nurse', 'Designer', 'Marketing Manager'],
            'locations': [
                ['Darlinghurst', 'Surry Hills', 'Kings Cross'],
                ['Newtown', 'Enmore', 'Marrickville'],
                ['Bondi', 'Coogee', 'Maroubra'],
                ['North Sydney', 'Crows Nest', 'Chatswood']
            ],
            'interests': ['Reading', 'Cooking', 'Hiking', 'Music', 'Photography', 'Yoga', 'Gaming', 'Travel'],
            'languages': ['English', 'Spanish', 'Mandarin', 'French', 'German', 'Italian'],
            'bios': [
                "I'm a friendly and clean person looking for like-minded roommates. I enjoy cooking and would love to share meals together!",
                "Professional working in tech, clean and respectful. Looking for a quiet place to call home.",
                "Student seeking affordable accommodation with other students or young professionals. Love music and outdoor activities.",
                "Easy-going person who values cleanliness and good communication. Happy to help with household chores.",
                "Creative professional looking for inspiring living space with interesting roommates."
            ]
        }

        created_users = []

        for i in range(count):
            # Create user
            email = f'testuser{i+1}@example.com'

            if User.objects.filter(email=email).exists():
                self.stdout.write(
                    self.style.WARNING(f'User {email} already exists, skipping')
                )
                continue

            user = User.objects.create_user(
                email=email,
                password='testpass123',
                first_name=f'TestUser{i+1}',
                last_name='Demo',
                email_verified=True,
                profile_completed=True
            )

            # Create profile with sample data
            profile = UserProfile.objects.create(
                user=user,
                date_of_birth=date(1990 + random.randint(0, 15), random.randint(1, 12), random.randint(1, 28)),
                gender=random.choice(['male', 'female', 'non_binary']),
                occupation=random.choice(sample_data['occupations']),
                education_level=random.choice(['bachelor', 'master', 'high_school']),
                preferred_locations=random.choice(sample_data['locations']),
                max_commute_time=random.randint(20, 60),
                has_car=random.choice([True, False]),
                min_budget=random.randint(200, 300),
                max_budget=random.randint(350, 500),
                preferred_room_type=random.choice(['private', 'shared', 'master']),
                lease_duration=random.choice(['medium', 'long', 'flexible']),
                move_in_date=date.today() + timedelta(days=random.randint(7, 60)),
                cleanliness_level=random.randint(6, 10),
                noise_tolerance=random.randint(3, 8),
                social_level=random.randint(4, 9),
                smoker=random.choice(['never', 'occasionally']),
                drinking=random.choice(['never', 'socially']),
                pets=random.choice(['none', 'cat', 'dog']),
                schedule_type=random.choice(['regular', 'flexible', 'student']),
                works_from_home=random.choice([True, False]),
                preferred_age_min=random.randint(20, 25),
                preferred_age_max=random.randint(30, 40),
                preferred_gender=random.choice(['any', 'same']),
                max_roommates=random.randint(2, 4),
                bio=random.choice(sample_data['bios']),
                interests=random.sample(sample_data['interests'], random.randint(3, 6)),
                languages=random.sample(sample_data['languages'], random.randint(1, 3)),
            )

            created_users.append(user.email)
            self.stdout.write(
                self.style.SUCCESS(f'Created user: {user.email} with profile ({profile.completion_percentage}% complete)')
            )

        if created_users:
            self.stdout.write(
                self.style.SUCCESS(f'\nSuccessfully created {len(created_users)} test users')
            )
            self.stdout.write('Login credentials: password is "testpass123" for all test users')
        else:
            self.stdout.write(
                self.style.WARNING('No new users were created')
            )