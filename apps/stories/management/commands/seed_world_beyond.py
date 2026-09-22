"""
Management command to seed the official "The World Beyond" story and anime.

Usage:
    python manage.py seed_world_beyond

Idempotent: re-running updates existing records instead of duplicating.
Creates the official author, project, story, chapters, scenes, characters,
animation project, and episodes.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.animation.models import AnimationProject, Episode
from apps.characters.models import Character
from apps.chapters.models import Chapter
from apps.projects.models import Project
from apps.scenes.models import Scene
from apps.stories.models import Genre, Story, Tag

User = get_user_model()

STORY_META = {
    "title": "The World Beyond",
    "description": (
        "An original MANJI story. Kai discovers that the world he knows is only one layer of reality "
        "— and a door has just opened in his bedroom."
    ),
    "content_type": "novel",
    "language": "en",
    "author_username": "Manji",
    "genres": ["Fantasy", "Adventure", "Drama"],
    "tags": ["manji-original", "official", "the-world-beyond", "anime"],
}

PROJECT_META = {
    "title": "The World Beyond",
    "description": "Official MANJI project for The World Beyond story and anime.",
    "project_type": "animation",
    "art_style": "anime",
    "art_style_description": "Modern 2D anime style with clean lines and cinematic lighting.",
    "status": "active",
}

CHARACTERS = [
    {
        "name": "Kai",
        "role": "protagonist",
        "age": 17,
        "bio": "A curious high school student who discovers a door in his bedroom that shouldn't exist.",
        "personality": "Curious, determined, guarded, quick-witted.",
        "backstory": "Grew up in a quiet neighborhood, always feeling like there was more to the world than what he could see.",
        "appearance": "Messy black hair, grey eyes, worn navy jacket, slim build.",
        "notes": "Protagonist. Drives the central mystery forward.",
    },
    {
        "name": "Ara",
        "role": "supporting",
        "age": 16,
        "bio": "A mysterious guide from the world beyond who appears at exactly the wrong — and right — moment.",
        "personality": "Playful, enigmatic, fiercely loyal, oddly calm.",
        "backstory": "Has been watching the boundary between worlds for years. Knows more than she reveals.",
        "appearance": "Silver-white hair tied in a loose braid, amber eyes, light armor with glowing runes.",
        "notes": "Primary companion. Voice of the world beyond.",
    },
    {
        "name": "The Curator",
        "role": "mentor",
        "age": None,
        "bio": "An ancient guardian of the boundary between worlds. Speaks in riddles but never lies.",
        "personality": "Wise, cryptic, patient, occasionally mischievous.",
        "backstory": "Has maintained the boundary for longer than anyone can remember. Once was mortal.",
        "appearance": "Tall figure in layered robes, face half-hidden by a mask of shifting light.",
        "notes": "Mentor figure. Provides exposition and rules of the world.",
    },
]

CHAPTERS = [
    {
        "number": 1,
        "title": "The Door",
        "content": (
            "Kai's bedroom was the same as it had always been — except for the writing on the wall. "
            "Not words he recognized. Not words he could pronounce. Just shapes that seemed to breathe "
            "when he looked at them too long. He pressed his palm against the plaster and felt warmth "
            "pulse back, like a heartbeat trapped in the drywall. Outside, the neighborhood was quiet. "
            "Inside, something was about to change forever."
        ),
        "scenes": [
            {
                "title": "Bedroom",
                "description": "Kai notices strange writing on his bedroom wall that pulses with warmth.",
                "location": "Kai's bedroom",
                "mood": "mysterious",
                "duration": 45,
                "camera_type": "wide_shot",
                "dialogue": "",
                "narration": (
                    "The room was ordinary in every way a room can be ordinary. A desk. A window. "
                    "A shelf of books he had never finished. But the writing on the wall was not ordinary. "
                    "It shifted when he blinked."
                ),
                "characters": ["Kai"],
            },
            {
                "title": "Laptop",
                "description": "The strange symbols appear on Kai's laptop screen.",
                "location": "Kai's desk",
                "mood": "tense",
                "duration": 60,
                "camera_type": "close_up",
                "dialogue": "Kai: What is this?",
                "narration": (
                    "The symbols migrated from the wall to his laptop, rearranging themselves like living text. "
                    "Kai typed a question. The symbols pulsed once, then resolved into a single word he somehow understood: "
                    "READY."
                ),
                "characters": ["Kai"],
            },
            {
                "title": "Portal",
                "description": "A door opens in Kai's bedroom, leading to a world he has never seen.",
                "location": "Kai's bedroom",
                "mood": "awe",
                "duration": 90,
                "camera_type": "establishing_shot",
                "dialogue": "Kai: I don't believe this. Ara: Belief is overrated. Step through.",
                "narration": (
                    "The door was not there a moment before. One breath later, it stood open — "
                    "a frame of light in the middle of his bedroom, humming with a sound like distant wind. "
                    "Beyond it, a sky the color of dawn stretched over a city of floating towers."
                ),
                "characters": ["Kai", "Ara"],
            },
        ],
    },
    {
        "number": 2,
        "title": "Arrival",
        "content": (
            "The world beyond was nothing like Kai had imagined. It was better. It was worse. "
            "It was simply more. Ara led him through streets that curved upward, past markets selling "
            "fruit that glowed from within, toward a tower that stood at the center of everything. "
            "The Curator waited inside, as he always knew Kai would come."
        ),
        "scenes": [
            {
                "title": "Floating City",
                "description": "Kai steps into a city where streets curve upward and buildings float.",
                "location": "The World Beyond — Central District",
                "mood": "wonder",
                "duration": 75,
                "camera_type": "wide_shot",
                "dialogue": "Kai: This is... real? Ara: As real as you are.",
                "narration": (
                    "Gravity here was a suggestion, not a law. Buildings floated in clusters, "
                    "tethered by chains of light. People moved along pathways that bent like vines. "
                    "The air smelled like ozone and jasmine."
                ),
                "characters": ["Kai", "Ara"],
            },
            {
                "title": "The Curator",
                "description": "Kai meets the ancient guardian of the boundary between worlds.",
                "location": "The Curator's tower",
                "mood": "solemn",
                "duration": 60,
                "camera_type": "medium_shot",
                "dialogue": "Curator: You are early. Kai: Am I? Curator: No. The door was.",
                "narration": (
                    "The Curator did not stand. He did not need to. His presence filled the room "
                    "like candlelight — warm, inevitable, impossible to ignore. The mask he wore "
                    "reflected nothing, yet Kai felt seen more deeply than ever before."
                ),
                "characters": ["Kai", "Ara", "The Curator"],
            },
            {
                "title": "The Rule",
                "description": "The Curator explains the single law of the world beyond.",
                "location": "The Curator's tower — upper chamber",
                "mood": "mysterious",
                "duration": 50,
                "camera_type": "over_the_shoulder",
                "dialogue": "Curator: Here, every choice writes itself into the sky. Choose carefully.",
                "narration": (
                    "There was only one rule, the Curator said. Not a law enforced by guards "
                    "or walls, but a truth woven into the air itself: every choice left a mark. "
                    "Not on paper. Not on skin. On the sky itself, where anyone could read it."
                ),
                "characters": ["Kai", "The Curator"],
            },
        ],
    },
    {
        "number": 3,
        "title": "Choice",
        "content": (
            "A way back opened. Kai stood at the threshold of two worlds. Behind him, the ordinary life "
            "he had always known — homework, empty hallways, the small noise of being a teenager. "
            "Before him, a world that needed someone who could see beyond the door. "
            "Ara watched. The Curator watched. The sky itself seemed to hold its breath."
        ),
        "scenes": [
            {
                "title": "Return",
                "description": "A door appears that would return Kai to his old world.",
                "location": "Boundary chamber",
                "mood": "bittersweet",
                "duration": 55,
                "camera_type": "medium_shot",
                "dialogue": "Ara: It will stay open for a while. Curator: It will always stay open.",
                "narration": (
                    "The door back was smaller than the one he had arrived through, as if the world "
                    "were reluctant to let him leave. Light spilled through it — ordinary light, "
                    "the kind that came from streetlamps and late afternoon sun. A life without magic."
                ),
                "characters": ["Kai", "Ara", "The Curator"],
            },
            {
                "title": "Stay",
                "description": "Kai realizes he does not want to go back.",
                "location": "Boundary chamber",
                "mood": "determined",
                "duration": 65,
                "camera_type": "close_up",
                "dialogue": "Kai: I'm not going back. Ara: I know. Curator: The sky already knows too.",
                "narration": (
                    "He looked at the door. Then at the sky. Then at Ara, who was smiling for the first time "
                    "since he had arrived. The choice was not hard. It was the easiest thing he had ever done. "
                    "He simply turned away from the door."
                ),
                "characters": ["Kai", "Ara", "The Curator"],
            },
            {
                "title": "Beginning",
                "description": "Kai takes his first real step into the world beyond.",
                "location": "The World Beyond — boundary edge",
                "mood": "hope",
                "duration": 80,
                "camera_type": "tracking_shot",
                "dialogue": "Kai: So what now? Ara: Now? Now the story begins.",
                "narration": (
                    "The sky changed color the moment he decided. From dawn to full day, "
                    "as if the world itself had been waiting for him to commit. Behind him, "
                    "the door faded. Ahead, a path descended into a valley of light. "
                    "His old life was a chapter closed. The world beyond was a blank page."
                ),
                "characters": ["Kai", "Ara"],
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Seed the official 'The World Beyond' story, anime project, characters, and episodes."

    def _get_or_create_official_user(self):
        user, _ = User.objects.get_or_create(
            username__iexact=STORY_META["author_username"],
            defaults={
                "username": STORY_META["author_username"],
                "email": f"{STORY_META['author_username'].lower()}@manji.app",
                "role": "creator",
                "is_official": True,
                "is_staff": False,
                "is_superuser": False,
            },
        )
        user.role = "creator"
        user.is_official = True
        user.save()
        return user

    def _ensure_genres_and_tags(self):
        genres = []
        for name in STORY_META["genres"]:
            genre, _ = Genre.objects.get_or_create(name=name)
            genres.append(genre)
        tags = []
        for name in STORY_META["tags"]:
            tag, _ = Tag.objects.get_or_create(name=name)
            tags.append(tag)
        return genres, tags

    def _create_project(self, author):
        project, _ = Project.objects.get_or_create(
            title=PROJECT_META["title"],
            defaults={
                "owner": author,
                "description": PROJECT_META["description"],
                "project_type": PROJECT_META["project_type"],
                "art_style": PROJECT_META["art_style"],
                "art_style_description": PROJECT_META["art_style_description"],
                "status": PROJECT_META["status"],
            },
        )
        return project

    def _create_story(self, author, project, genres, tags):
        story, _ = Story.objects.get_or_create(
            slug="the-world-beyond",
            defaults={
                "title": STORY_META["title"],
                "description": STORY_META["description"],
                "content_type": STORY_META["content_type"],
                "language": STORY_META["language"],
                "author": author,
                "status": Story.Status.PUBLISHED,
                "is_premium": False,
                "is_featured": True,
                "is_official": True,
            },
        )
        story.genres.set(genres)
        story.tags.set(tags)
        if project.story != story:
            project.story = story
            project.save()
        return story

    def _create_characters(self, project):
        character_map = {}
        for data in CHARACTERS:
            char, _ = Character.objects.get_or_create(
                project=project,
                name=data["name"],
                defaults={
                    "role": data["role"],
                    "age": data["age"],
                    "bio": data["bio"],
                    "personality": data["personality"],
                    "backstory": data["backstory"],
                    "appearance": data["appearance"],
                    "notes": data["notes"],
                },
            )
            character_map[data["name"]] = char
        return character_map

    def _create_chapters_and_scenes(self, project, story, character_map):
        chapter_map = {}
        for chapter_data in CHAPTERS:
            chapter, _ = Chapter.objects.update_or_create(
                story=story,
                chapter_number=chapter_data["number"],
                defaults={
                    "title": chapter_data["title"],
                    "content": chapter_data["content"],
                    "status": Chapter.Status.PUBLISHED,
                    "is_premium": False,
                },
            )
            word_count = len(chapter_data["content"].split())
            Chapter.objects.filter(pk=chapter.pk).update(
                word_count=word_count,
                reading_time=max(1, word_count // 200),
            )
            chapter.refresh_from_db()
            chapter_map[chapter_data["number"]] = chapter

            for idx, scene_data in enumerate(chapter_data["scenes"], start=1):
                cast_ids = [character_map[name].id for name in scene_data.get("characters", [])]
                Scene.objects.update_or_create(
                    project=project,
                    chapter=chapter,
                    title=scene_data["title"],
                    defaults={
                        "description": scene_data.get("description", ""),
                        "location": scene_data.get("location", ""),
                        "mood": scene_data.get("mood", ""),
                        "duration": scene_data.get("duration"),
                        "camera_type": scene_data.get("camera_type", ""),
                        "camera_notes": "",
                        "dialogue": scene_data.get("dialogue", ""),
                        "narration": scene_data.get("narration", ""),
                        "order": idx,
                    },
                )
                scene = Scene.objects.get(project=project, chapter=chapter, title=scene_data["title"])
                scene.cast.set(cast_ids)
        return chapter_map

    def _create_animation_and_episodes(self, project):
        animation, _ = AnimationProject.objects.get_or_create(
            project=project,
            title=f"{PROJECT_META['title']} — Official Anime",
            defaults={
                "fps": 12,
                "width": 1920,
                "height": 1080,
            },
        )
        for idx in range(1, len(CHAPTERS) + 1):
            Episode.objects.update_or_create(
                animation=animation,
                episode_number=idx,
                defaults={
                    "title": f"Episode {idx} — {CHAPTERS[idx - 1]['title']}",
                    "description": f"Based on Chapter {idx} of The World Beyond.",
                    "status": Episode.Status.DRAFT,
                },
            )
        return animation

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Seeding The World Beyond..."))

        author = self._get_or_create_official_user()
        self.stdout.write(self.style.SUCCESS(f"Official author ready: {author.username}"))

        genres, tags = self._ensure_genres_and_tags()
        self.stdout.write(self.style.SUCCESS(f"Genres and tags ready: {len(genres)} genres, {len(tags)} tags"))

        project = self._create_project(author)
        self.stdout.write(self.style.SUCCESS(f"Project ready: {project.title} (type={project.project_type}, style={project.art_style})"))

        story = self._create_story(author, project, genres, tags)
        self.stdout.write(self.style.SUCCESS(f"Story ready: {story.title} (slug={story.slug}, official={story.is_official})"))

        character_map = self._create_characters(project)
        self.stdout.write(self.style.SUCCESS(f"Characters ready: {len(character_map)} characters"))

        self._create_chapters_and_scenes(project, story, character_map)
        self.stdout.write(self.style.SUCCESS(f"Chapters and scenes ready: {len(CHAPTERS)} chapters"))

        animation = self._create_animation_and_episodes(project)
        self.stdout.write(self.style.SUCCESS(f"Animation project ready: {animation.title}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\nThe World Beyond is ready:\n"
                f"  Story: {story.title} (slug={story.slug})\n"
                f"  Project: {project.title} (id={project.id})\n"
                f"  Animation: {animation.title} (id={animation.id})\n"
                f"  Chapters: {len(CHAPTERS)}\n"
                f"  Episodes: {animation.episodes.count()}\n"
            )
        )
