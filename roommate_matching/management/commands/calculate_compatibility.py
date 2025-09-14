from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from roommate_matching.services import MatchingService
from roommate_matching.models import CompatibilityScore

User = get_user_model()


class Command(BaseCommand):
    help = 'Calculate compatibility scores for users or generate recommendations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='Calculate compatibility for specific user ID',
        )
        parser.add_argument(
            '--all-users',
            action='store_true',
            help='Calculate compatibility for all users',
        )
        parser.add_argument(
            '--recommendations',
            action='store_true',
            help='Generate recommendations for users',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Limit number of recommendations per user',
        )

    def handle(self, *args, **options):
        matching_service = MatchingService()

        if options['user_id']:
            user = User.objects.get(id=options['user_id'])
            self.stdout.write(f"Processing user: {user.get_short_name()} ({user.email})")

            if options['recommendations']:
                recommendations = matching_service.generate_recommendations(user, limit=options['limit'])
                self.stdout.write(f"Generated {len(recommendations)} recommendations")

                for rec in recommendations[:5]:  # Show top 5
                    self.stdout.write(
                        f"  - {rec.recommended_user.get_short_name()}: "
                        f"{rec.compatibility_score.overall_score:.1f}% "
                        f"({rec.compatibility_score.compatibility_level})"
                    )
            else:
                # Calculate with other users
                other_users = User.objects.filter(
                    profile_completed=True,
                    is_active=True
                ).exclude(id=user.id)[:5]  # Limit for testing

                for other_user in other_users:
                    try:
                        score = matching_service.calculate_user_compatibility(user, other_user)
                        self.stdout.write(
                            f"  {user.get_short_name()} ↔ {other_user.get_short_name()}: "
                            f"{score.overall_score:.1f}% ({score.compatibility_level})"
                        )
                    except Exception as e:
                        self.stdout.write(f"  Error with {other_user.get_short_name()}: {str(e)}")

        elif options['all_users']:
            users = User.objects.filter(profile_completed=True, is_active=True)
            self.stdout.write(f"Processing {users.count()} users...")

            if options['recommendations']:
                for user in users:
                    try:
                        recommendations = matching_service.generate_recommendations(
                            user,
                            limit=options['limit']
                        )
                        self.stdout.write(
                            f"{user.get_short_name()}: {len(recommendations)} recommendations"
                        )
                    except Exception as e:
                        self.stdout.write(f"Error for {user.get_short_name()}: {str(e)}")
            else:
                # Calculate pairwise compatibility
                user_list = list(users)
                total_pairs = 0

                for i, user1 in enumerate(user_list):
                    for user2 in user_list[i+1:]:
                        try:
                            score = matching_service.calculate_user_compatibility(user1, user2)
                            total_pairs += 1
                            if total_pairs % 10 == 0:
                                self.stdout.write(f"Processed {total_pairs} pairs...")
                        except Exception as e:
                            self.stdout.write(f"Error: {user1.get_short_name()} ↔ {user2.get_short_name()}: {str(e)}")

                self.stdout.write(f"Calculated {total_pairs} compatibility scores")
        else:
            # Show existing scores
            scores = CompatibilityScore.objects.select_related(
                'user1', 'user2'
            ).order_by('-overall_score')[:10]

            self.stdout.write("Top 10 compatibility scores:")
            for score in scores:
                self.stdout.write(
                    f"  {score.user1.get_short_name()} ↔ {score.user2.get_short_name()}: "
                    f"{score.overall_score:.1f}% ({score.compatibility_level})"
                )

        self.stdout.write(self.style.SUCCESS('Done!'))