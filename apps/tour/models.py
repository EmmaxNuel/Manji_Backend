"""
Tour state – additive progress-tracking storage for the in-app tour guide.

Tied 1:1 to the user so the post-registration prompt and seen-tours tracking
persist across devices and browser sessions. This app deliberately touches no
existing models or business logic.
"""

from django.conf import settings
from django.db import models


class TourState(models.Model):
    class PostRegistration(models.TextChoices):
        NONE = "none", "Not prompted"
        PROMPTED = "prompted", "Prompted"
        SKIPPED = "skipped", "Skipped"
        COMPLETED = "completed", "Completed"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tour_state",
        primary_key=True,
    )

    # Post-registration prompt lifecycle.
    post_registration = models.CharField(
        max_length=15,
        choices=PostRegistration.choices,
        default=PostRegistration.NONE,
        db_index=True,
    )
    post_registration_prompted_at = models.DateTimeField(null=True, blank=True)
    post_registration_answered_at = models.DateTimeField(null=True, blank=True)

    # Which tours the user has seen: {tour_key: ISO timestamp}.
    # Completed/skipped contextual tours do not auto-replay, but can always be
    # replayed on request from the "Take a tour" entry point.
    completed_tours = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tour_state"

    def __str__(self):
        return f"TourState({self.user.username}: {self.post_registration})"

    def mark_post_registration(self, state):
        """Record prompted/skipped/completed for the post-registration prompt."""
        self.post_registration = state
        if self.post_registration_prompted_at is None:
            from django.utils import timezone
            self.post_registration_prompted_at = timezone.now()
        if state in (self.PostRegistration.SKIPPED, self.PostRegistration.COMPLETED):
            from django.utils import timezone
            self.post_registration_answered_at = timezone.now()
        self.save(update_fields=[
            "post_registration",
            "post_registration_prompted_at",
            "post_registration_answered_at",
            "updated_at",
        ])

    def complete_tour(self, tour_key):
        """Record a tour as seen (won't auto-replay, replay still allowed)."""
        from django.utils import timezone
        self.completed_tours[tour_key] = timezone.now().isoformat()
        self.save(update_fields=["completed_tours", "updated_at"])