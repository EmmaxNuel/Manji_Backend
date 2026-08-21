"""
Management command to seed the Genre table with Manji's default genres.

Usage:
    python manage.py seed_genres
"""
from django.core.management.base import BaseCommand
from apps.stories.models import Genre


GENRES = [
    {"name": "Fantasy",      "color": "#7c3aed", "description": "Magic, mythical creatures, and imagined worlds."},
    {"name": "Romance",      "color": "#ec4899", "description": "Love stories and romantic relationships."},
    {"name": "Action",       "color": "#ef4444", "description": "High-energy stories full of fights and battles."},
    {"name": "Adventure",    "color": "#f97316", "description": "Journeys, exploration, and quests."},
    {"name": "Mystery",      "color": "#6366f1", "description": "Puzzles, secrets, and detective work."},
    {"name": "Thriller",     "color": "#dc2626", "description": "Suspense, danger, and high stakes."},
    {"name": "Sci-Fi",       "color": "#06b6d4", "description": "Science, technology, and speculative futures."},
    {"name": "Horror",       "color": "#1e1b4b", "description": "Fear, dread, and the supernatural."},
    {"name": "Comedy",       "color": "#fbbf24", "description": "Humour, wit, and lighthearted stories."},
    {"name": "Drama",        "color": "#8b5cf6", "description": "Emotional, character-driven narratives."},
    {"name": "Slice of Life","color": "#22c55e", "description": "Everyday life and relatable situations."},
    {"name": "Historical",   "color": "#92400e", "description": "Set in historical periods or events."},
    {"name": "Psychological","color": "#4f46e5", "description": "Mind games, identity, and inner conflict."},
    {"name": "Supernatural", "color": "#7e22ce", "description": "Ghosts, spirits, and the paranormal."},
    {"name": "Sports",       "color": "#16a34a", "description": "Competition, training, and athletic life."},
    {"name": "School Life",  "color": "#0ea5e9", "description": "Stories set in school and student life."},
    {"name": "Isekai",       "color": "#a21caf", "description": "Characters transported to another world."},
    {"name": "Martial Arts", "color": "#b45309", "description": "Combat techniques, cultivation, and honour."},
    {"name": "Mecha",        "color": "#64748b", "description": "Giant robots and mechanical warfare."},
    {"name": "Cooking",      "color": "#d97706", "description": "Food, recipes, and culinary competition."},
]


class Command(BaseCommand):
    help = "Seed the database with default Manji genres."

    def handle(self, *args, **options):
        created = 0
        updated = 0

        for g in GENRES:
            obj, was_created = Genre.objects.update_or_create(
                name=g["name"],
                defaults={
                    "color": g["color"],
                    "description": g["description"],
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Genres seeded: {created} created, {updated} updated."
            )
        )
