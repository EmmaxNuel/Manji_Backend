from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from apps.official.models import (
    OfficialSeries, OfficialSeason, OfficialArc, OfficialStory, OfficialChapter,
    OfficialAnimation, OfficialEpisode,
)
from apps.stories.models import Story
from apps.chapters.models import Chapter
from .story_content import CHAPTERS

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed official MANJI content with "The World Beyond" story'

    def handle(self, *args, **options):
        self.stdout.write('Seeding official MANJI content...')

        # System author for official content
        author, _ = User.objects.get_or_create(
            email='official@manji.io',
            defaults={
                'username': 'manji_official',
                'role': User.Role.ADMIN,
                'is_official': True,
                'is_active': True,
            },
        )

        series, _ = OfficialSeries.objects.get_or_create(
            slug='manji',
            defaults={
                'title': 'MANJI',
                'description': 'The official MANJI universe - where ancient power meets modern destiny.',
                'tagline': 'OFFICIAL MANJI / MANJI ORIGINAL',
                'order': 1,
                'is_active': True,
            }
        )
        self.stdout.write(f'  Series: {series.title}')

        season, _ = OfficialSeason.objects.get_or_create(
            series=series,
            season_number=1,
            defaults={
                'title': 'Season 1: Awakening',
                'description': 'The journey begins as ancient seals break and forgotten powers stir.',
                'order': 1,
                'is_published': True,
            }
        )
        self.stdout.write(f'  Season: {season.title}')

        arc, _ = OfficialArc.objects.get_or_create(
            season=season,
            slug='the-world-beyond',
            defaults={
                'title': 'The World Beyond',
                'description': 'A young explorer discovers that the world they know is only a fraction of what exists beyond the veil.',
                'order': 1,
                'is_published': True,
            }
        )
        self.stdout.write(f'  Arc: {arc.title}')

        story_obj, _ = Story.objects.get_or_create(
            slug='the-world-beyond',
            defaults={
                'title': 'The World Beyond',
                'description': 'When the boundary between worlds fractures, a chosen few must navigate realms unknown to prevent total collapse.',
                'cover': '',
                'status': 'published',
                'is_official': True,
                'author': author,
                'content_type': 'novel',
            }
        )
        self.stdout.write(f'  Story: {story_obj.title}')

        official_story, _ = OfficialStory.objects.get_or_create(
            arc=arc,
            story=story_obj,
            defaults={'order': 1, 'is_canon': True}
        )

        for ch_data in CHAPTERS:
            chapter_obj, created = Chapter.objects.get_or_create(
                story=story_obj,
                chapter_number=ch_data['number'],
                defaults={
                    'title': ch_data['title'],
                    'content': self._build_chapter_content(ch_data),
                    'status': 'published',
                }
            )
            if not created:
                chapter_obj.content = self._build_chapter_content(ch_data)
                chapter_obj.title = ch_data['title']
                chapter_obj.status = 'published'
                chapter_obj.save()

            OfficialChapter.objects.get_or_create(
                official_story=official_story,
                chapter=chapter_obj,
                defaults={'order': ch_data['number'], 'is_published': True}
            )
            self.stdout.write(f'  Chapter {ch_data["number"]}: {ch_data["title"]}')

        # Official animation shell: series entry + trailer placeholder.
        # Honest by design — no video yet, so the episode carries an
        # "In Production" title/description and the app renders its
        # "video not available yet" placeholder. Replaced by real
        # episodes (with video) as animation is produced.
        animation, _ = OfficialAnimation.objects.get_or_create(
            slug='manji-the-world-beyond',
            defaults={
                'series': series,
                'arc': arc,
                'title': 'MANJI: The World Beyond',
                'description': (
                    'The animated adaptation of the official MANJI story. '
                    'Episodes appear here as animation is completed.'
                ),
                'order': 1,
                'is_published': True,
            }
        )
        self.stdout.write(f'  Animation: {animation.title}')

        trailer, created = OfficialEpisode.objects.get_or_create(
            animation=animation,
            episode_number=1,
            defaults={
                'title': 'Official Trailer — In Production',
                'description': (
                    'The official MANJI animated series is in production. '
                    'The trailer video will appear here once it is finished. '
                    'Meanwhile, read the story it adapts.'
                ),
                'order': 1,
                'is_published': True,
            }
        )
        if created:
            self.stdout.write(f'  Episode: {trailer.title}')
        else:
            self.stdout.write('  Episode: trailer already exists, kept as-is')

        self.stdout.write(self.style.SUCCESS('Successfully seeded official MANJI content!'))
        self.stdout.write(f'Total chapters: {len(CHAPTERS)}')

    def _build_chapter_content(self, chapter_data):
        content = f'# Chapter {chapter_data["number"]}: {chapter_data["title"]}\n\n'
        content += f'*{chapter_data["hook"]}*\n\n'
        for i, scene in enumerate(chapter_data['scenes'], 1):
            content += f'## Scene {i}: {scene["title"]}\n\n'
            content += scene['content'] + '\n\n'
        return content