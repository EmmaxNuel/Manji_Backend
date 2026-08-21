"""
Management command to seed the official "Welcome to Manji" welcome story.

Usage:
    python manage.py seed_manji_story

Idempotent: re-running updates the story and its chapters instead of
duplicating them. The official author account is created once with a random
password (printed to the console); the story itself is free (is_premium=False)
and is marked as official Manji platform content (is_official=True), so normal
users can never edit or delete it.
"""
import secrets
from datetime import timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from apps.chapters.models import Chapter
from apps.stories.models import Genre, Story, Tag
from apps.users.models import Profile

User = get_user_model()

STORY = {
    "title": "Welcome to Manji",
    "description": (
        "The official Manji welcome story — a journey through a home built for "
        "stories, creators, and readers. Every story has a beginning. This is yours."
    ),
    "content_type": "novel",
    "language": "en",
    "author_username": "Manji",
    "genres": ["Fantasy", "Adventure", "General"],
    "tags": ["manji", "welcome", "official", "new-to-manji", "getting-started"],
}

OFFICIAL_BIO = "Welcome to Manji — a home for stories, creators, and readers."

CHAPTERS = [
    {
        "number": 1,
        "title": "Prologue — Welcome to Manji",
        "content": """Somewhere, right now, a person is about to open a page and meet a stranger.
That stranger is you.
Or maybe you are the one about to arrive — carrying a half-finished idea, a sketch on the back of a napkin, a novel you have dreamed about for years, or simply the quiet wish to be moved by someone else's words.
Welcome to Manji.
This is not a building.
It is not a company.
It is not even really a website.
Manji is a place that exists because of one belief:
Everyone has a story worth telling.
Not every story is long. Not every story is loud. Some are whispered at midnight. Some are drawn in a single line. Some take a hundred chapters to begin.
But every single one of them matters.
If you have ever written a sentence, drawn a character, read past midnight, or fallen in love with someone who only existed on a page — you already belong here.
You have walked into a world made of words and pictures, built by hands like yours.
Take a breath.
Look around.
Every shelf you see was filled by someone who once had nothing but a blank page and the nerve to fill it.
And now there is room for one more.
Welcome to Manji.
""",
    },
    {
        "number": 2,
        "title": "Chapter 1 — The First Page",
        "content": """Every great journey begins the same way.
Not with a map. Not with an army. Not with perfect planning.
With a single page, and the choice to write on it.
Think of everything you love to read today. Someone, somewhere, once sat down with nothing — no guarantee of readers, no promise of applause — and typed a single sentence. Then another. Then another.
That first sentence is where it all began.
The same is true for a drawing.
Before a manga has its hundredth page, before a comic has its iconic cover, there is a first sketch. A character who existed only in someone's imagination, caught on paper for the very first time. A single line that became a face, a world, a life.
Inspiration rarely arrives fully formed.
It comes as a fragment. A feeling. A half-remembered dream. A voice you cannot quite name but cannot ignore.
The writers and artists of Manji know this secret:
The first page does not have to be perfect.
It only has to be brave.
Because the story does not live in the finished product. It lives in the moment someone decided to begin.
Somewhere inside you — maybe buried, maybe just waiting — there is a first page.
It has been waiting for you to be ready.
You are ready now.
""",
    },
    {
        "number": 3,
        "title": "Chapter 2 — The Writers",
        "content": """Walk down any street in your imagination and you will meet them.
The novelists. The poets. The web serial authors who post a chapter every single night without fail. The short story writers who can break your heart in two thousand words. The dreamers who spend years inside one world and call it their life's work.
These are the writers of Manji.
They bring characters to life with nothing more than words. A name. A habit. A fear. A choice.
Somewhere between the sentences, a stranger on a page stops being a stranger and becomes someone you would protect with your life.
That is not a trick.
That is the writer's quiet magic.
Writers on Manji write the stories only they can tell. Their voices fill this place with worlds you could walk into forever — thrillers that keep you up, romances that make you believe again, fantasy realms with maps you wish were real, and slice-of-life tales that feel like coming home.
They also teach us something important about beginnings.
No writer starts famous.
Every single one of them published a first chapter once, to silence, and kept going anyway.
They kept going because they believed a story — even one read by a single person — was worth finishing.
Here, we believe it too.
""",
    },
    {
        "number": 4,
        "title": "Chapter 3 — The Artists",
        "content": """Now look up from the words.
Everywhere around you, there are stories being told without a single sentence.
A single panel can hold more emotion than a paragraph. A splash page can take your breath away. A character design can become famous the moment the world sees it.
These are the artists of Manji — the comic creators, the manga storytellers, the manhua artists who make worlds you can see.
Every page they draw is a chapter. Every panel is a sentence. Every face they render is a character born of line, ink, and imagination.
Artists know a truth that writers also learn:
Storytelling is not one language. It is many.
Some stories are meant to be sung. Some are meant to be acted. And some — the ones we gather here for — are meant to be drawn.
A comic creator can spend a month on a single page because that page is a moment the reader will never forget.
A manga artist can hide an entire emotional arc in a single gaze.
A manhua artist can make an entire city feel alive in one establishing shot.
When a picture tells a story, it speaks directly to the heart. No translation needed.
That is the artist's gift to Manji.
And every panel you have ever loved was once a blank page — until someone dared to put the first line on it.
""",
    },
    {
        "number": 5,
        "title": "Chapter 4 — The Readers",
        "content": """A story on a page is only half of a story.
The other half is waiting for someone to find it.
Think about the last book that kept you reading until the light turned grey outside your window. The last manga chapter you finished and immediately wanted more of. The last novel that made you feel less alone.
You were not just reading.
You were completing something.
Every reader on Manji is doing that right now — discovering stories, following authors, leaving likes and comments that mean more than authors can say, and carrying characters in their hearts long after the final page.
Stories become meaningful when someone discovers them.
A story written and never read is like a letter never sent. But the moment a reader opens it — the moment someone's heart meets someone else's words — that letter is delivered. That story finally exists.
That is the reader's role, and it is sacred.
Readers are the reason writers keep writing.
Readers are the reason artists keep drawing.
Readers are the ones who decide which worlds deserve to live forever.
If you are a reader, you are not a bystander.
You are the very reason Manji exists at all.
""",
    },
    {
        "number": 6,
        "title": "Chapter 5 — A World of Stories",
        "content": """Now let us show you the whole map.
Manji is where every form of storytelling comes together under one sky.
Here you can:
Read novels that take you months to travel through.
Write stories and publish them to the world from the moment you finish the first chapter.
Create comics, frame by frame, panel by panel.
Read manga and manhua that arrived here from across the globe.
Discover new creators before anyone else knows their name.
Follow the authors and artists whose worlds you love.
And build an audience of your own — readers who will wait for your next chapter the way you once waited for theirs.
This is a rare thing in the world.
Most places ask you to choose: reader or writer, artist or audience.
Manji was built to refuse that choice.
A reader here can become a creator in an afternoon. A writer here can learn to see their story through an artist's eyes. An artist here can find the writer whose words they were born to draw.
Every role feeds the others.
Every story makes the world around it a little bigger.
And every person who arrives — every single one — becomes part of that world.
Including you.
""",
    },
    {
        "number": 7,
        "title": "Chapter 6 — Your Story",
        "content": """Let us pause here for a moment.
Everything you have read so far has been about other people.
The writers. The artists. The readers. The stories that already live in this place.
But there is one story we have not told yet.
Yours.
Not the story of who you are right now — that is still being written, and you will write it with every choice you make.
The story we mean is the one you have been carrying.
The idea you never started. The character you drew once and hid away. The novel you keep saying you will write someday. The comic you have pictured in perfect detail but never committed to a page.
It is here, waiting for you.
Manji is not complete without it.
Because this place was never about collecting stories. It was about giving every person on earth a home for the one story only they can tell.
You do not need permission.
You do not need to be good yet.
You do not need to know how it ends.
You only need to begin.
Somewhere in this world, a future reader is waiting for the first chapter of your story. They do not know you yet. They have not met your characters. They are out there, with a heart that is ready to be moved.
And they are waiting.
""",
    },
    {
        "number": 8,
        "title": "Chapter 7 — The First Word",
        "content": """Every journey in Manji ends the same way it begins.
With a single word.
Not a grand declaration. Not a perfect sentence. Just one word, placed onto a blank page by someone who decided to start.
That word is yours to choose.
It might be the first line of a novel.
It might be the name of a character.
It might be the title of the comic you have been dreaming about.
It might simply be the word "yes" — yes, I am a storyteller. Yes, I belong here.
Whatever you choose, choose it today.
Because the door you walked through is not meant to close behind you.
It is meant to open into everything you have not written yet.
You've found Manji. Now, what story will you leave behind?
""",
    },
]


class Command(BaseCommand):
    help = "Seed the official 'Welcome to Manji' welcome story into the app."

    def _font(self, size):
        for candidate in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ):
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
        return ImageFont.load_default()

    def _set_official_avatar(self, author, profile):
        """Generate a simple "M" avatar for the official account."""
        try:
            img = Image.new("RGB", (256, 256), "#0a0a12")
            draw = ImageDraw.Draw(img)
            draw.ellipse((16, 16, 240, 240), fill="#f97316")
            draw.ellipse((64, 64, 192, 192), fill="#0a0a12")
            draw.text((80, 84), "M", font=self._font(96), fill="#f97316")
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            profile.avatar.save(
                "manji_avatar.png", ContentFile(buffer.getvalue()), save=True
            )
            self.stdout.write(self.style.SUCCESS("Generated official avatar."))
        except Exception as exc:  # pragma: no cover - best effort
            self.stdout.write(self.style.WARNING(f"Avatar generation skipped: {exc}"))

    def _set_official_cover(self, story):
        """Generate the distinctive official "Welcome to Manji" cover (Pillow, best effort)."""
        try:
            width, height = 800, 1200
            img = Image.new("RGB", (width, height), "#0b0b14")
            draw = ImageDraw.Draw(img)

            # Deep vertical gradient
            for i in range(height):
                shade = int(11 + 30 * (i / height))
                draw.line([(0, i), (width, i)], fill=(shade, shade, shade + 9))

            # Ember glow circle
            glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            gd = ImageDraw.Draw(glow)
            gd.ellipse((170, 240, 630, 700), fill=(249, 115, 22, 60))
            gd.ellipse((270, 340, 530, 600), fill=(249, 115, 22, 45))
            img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
            draw = ImageDraw.Draw(img)

            # Border frame
            draw.rectangle(
                (48, 48, width - 48, height - 48), outline=(249, 115, 22, 255), width=4
            )

            # Eyebrow badge
            badge_font = self._font(40)
            badge = "OFFICIAL MANJI STORY"
            bbox = draw.textbbox((0, 0), badge, font=badge_font)
            draw.rounded_rectangle(
                (320, 180, 480, 240),
                radius=30,
                fill=(249, 115, 22, 255),
            )
            draw.text(
                (400 - (bbox[2] - bbox[0]) / 2, 196),
                badge,
                font=badge_font,
                fill=(10, 10, 18),
            )

            # Title
            title_font = self._font(88)
            for i, line in enumerate(["Welcome to", "Manji"]):
                bbox = draw.textbbox((0, 0), line, font=title_font)
                tw = bbox[2] - bbox[0]
                draw.text(
                    ((width - tw) / 2, 330 + i * 110),
                    line,
                    font=title_font,
                    fill=(255, 255, 255),
                )

            # Tagline
            tagline_font = self._font(42)
            tagline = "A home for stories, creators, and readers."
            bbox = draw.textbbox((0, 0), tagline, font=tagline_font)
            tw = bbox[2] - bbox[0]
            draw.text(
                ((width - tw) / 2, 600),
                tagline,
                font=tagline_font,
                fill=(249, 115, 22, 255),
            )

            # Sub-line
            sub_font = self._font(38)
            sub = "Every story has a beginning. This is yours."
            bbox = draw.textbbox((0, 0), sub, font=sub_font)
            tw = bbox[2] - bbox[0]
            draw.text(
                ((width - tw) / 2, 690),
                sub,
                font=sub_font,
                fill=(210, 210, 225),
            )

            # Author line
            author_font = self._font(42)
            by = "by Manji"
            bbox = draw.textbbox((0, 0), by, font=author_font)
            tw = bbox[2] - bbox[0]
            draw.text(
                ((width - tw) / 2, 900),
                by,
                font=author_font,
                fill=(255, 255, 255),
            )

            buffer = BytesIO()
            img.save(buffer, format="PNG")
            story.cover.save("manji_cover.png", ContentFile(buffer.getvalue()), save=True)
            self.stdout.write(self.style.SUCCESS("Generated official cover."))
        except Exception as exc:  # pragma: no cover - best effort
            self.stdout.write(self.style.WARNING(f"Cover generation skipped: {exc}"))

    def handle(self, *args, **options):
        # 1) Official author
        author, created = User.objects.get_or_create(
            username__iexact=STORY["author_username"],
            defaults={
                "username": STORY["author_username"],
                "email": f"{STORY['author_username'].lower()}@manji.app",
                "role": "creator",
                "is_official": True,
                "is_staff": False,
                "is_superuser": False,
            },
        )
        if created:
            author.set_password(secrets.token_urlsafe(16))
            author.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created official author '{author.username}' "
                    f"(random password, do not use to log in)."
                )
            )
        else:
            author.role = "creator"
            author.is_official = True
            author.save()
            self.stdout.write(self.style.NOTICE(f"Reusing author '{author.username}'."))

        # Official profile bio + avatar
        profile, _ = Profile.objects.get_or_create(user=author)
        if profile.bio != OFFICIAL_BIO:
            profile.bio = OFFICIAL_BIO
            profile.save()
        self._set_official_avatar(author, profile)

        # 2) Genres & tags
        genres = []
        for name in STORY["genres"]:
            genre, _ = Genre.objects.get_or_create(name=name)
            genres.append(genre)

        tags = []
        for name in STORY["tags"]:
            tag, _ = Tag.objects.get_or_create(name=name)
            tags.append(tag)

        # 3) Story
        story, story_created = Story.objects.get_or_create(
            slug="manji",
            defaults={
                "title": STORY["title"],
                "description": STORY["description"],
                "content_type": STORY["content_type"],
                "language": STORY["language"],
                "author": author,
                "status": Story.Status.PUBLISHED,
                "is_premium": False,
                "is_featured": True,
                "is_official": True,
            },
        )
        if story_created:
            self.stdout.write(self.style.SUCCESS(f"Created story '{story.title}'."))
        else:
            # Keep metadata in sync on re-runs
            story.title = STORY["title"]
            story.description = STORY["description"]
            story.content_type = STORY["content_type"]
            story.language = STORY["language"]
            story.author = author
            story.status = Story.Status.PUBLISHED
            story.is_premium = False
            story.is_featured = True
            story.is_official = True
            story.save()
            self.stdout.write(self.style.NOTICE(f"Updated story '{story.title}'."))

        story.genres.set(genres)
        story.tags.set(tags)

        self._set_official_cover(story)

        # Clean up the legacy seed author now that the story is reassigned
        legacy = User.objects.filter(username__iexact="kai_manji").first()
        if legacy and legacy != author and not legacy.authored_stories.exists():
            legacy.delete()
            self.stdout.write(self.style.NOTICE("Removed legacy seed author 'kai_manji'."))

        # 4) Chapters
        base_published_at = timezone.now()
        chapter_numbers = [c["number"] for c in CHAPTERS]
        for chapter_data in CHAPTERS:
            chapter, chapter_created = Chapter.objects.update_or_create(
                story=story,
                chapter_number=chapter_data["number"],
                defaults={
                    "title": chapter_data["title"],
                    "content": chapter_data["content"],
                    "status": Chapter.Status.PUBLISHED,
                    "is_premium": False,
                    "published_at": base_published_at
                    + timedelta(hours=chapter_data["number"]),
                },
            )
            # Ensure denormalized metrics reflect the seeded content
            word_count = len(chapter_data["content"].split())
            Chapter.objects.filter(pk=chapter.pk).update(
                word_count=word_count,
                reading_time=max(1, word_count // 200),
            )
            chapter.refresh_from_db()
            status_text = "Created" if chapter_created else "Updated"
            self.stdout.write(
                f"  {self.style.MIGRATE_HEADING(status_text)} "
                f"chapter {chapter.chapter_number}: {chapter.title} "
                f"({chapter.word_count} words)"
            )

        # Remove any leftover chapters from previous seed versions
        stale = story.chapters.exclude(chapter_number__in=chapter_numbers)
        if stale.exists():
            stale.delete()
            self.stdout.write(
                self.style.NOTICE(
                    f"Removed {stale.count()} stale chapters no longer part of the story."
                )
            )

        # 5) Recalculate denormalized story metrics
        published_chapters = story.chapters.filter(status="published")
        total_words = sum(ch.word_count for ch in published_chapters)
        total_read_time = sum(ch.reading_time for ch in published_chapters)
        Story.objects.filter(pk=story.pk).update(
            chapters_count=published_chapters.count(),
            word_count=total_words,
            avg_reading_time=total_read_time,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Story '{story.title}' ready: "
                f"{published_chapters.count()} chapters, "
                f"{total_words} words, free & published at "
                f"{story.published_at.isoformat()}."
            )
        )