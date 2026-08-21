"""
Chapter signals – keep the parent Story's aggregates in sync.

The Story model stores denormalized counters (chapters_count, word_count,
avg_reading_time). Before this module those were only refreshed by the seed
command and on chapter create/delete, so a chapter publish/edit would leave
them stale. These signals recompute them on every chapter save/delete.

Semantics (kept consistent with the seed command):
- chapters_count   – number of *published* chapters
- word_count       – total words of *published* chapters
- avg_reading_time – total reading minutes of *published* chapters

Draft-only words are intentionally excluded so public story pages never show
unpublished content metrics. The studio's writing-progress view computes its
own totals that include drafts.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.stories.models import Story

from .models import Chapter


@receiver([post_save, post_delete], sender=Chapter)
def sync_story_aggregates(sender, instance, **kwargs):
    story_id = instance.story_id
    if not story_id:
        return

    published = Chapter.objects.filter(story_id=story_id, status=Chapter.Status.PUBLISHED)
    Story.objects.filter(pk=story_id).update(
        chapters_count=published.count(),
        word_count=sum(published.values_list("word_count", flat=True)),
        avg_reading_time=sum(published.values_list("reading_time", flat=True)),
    )
