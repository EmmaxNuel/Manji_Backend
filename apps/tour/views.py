"""
Tour state API.

- GET  /api/tour/              – current tour state for the caller
- POST /api/tour/record/       – record a tour event

Record events (JSON body):
  {"event": "post_registration_prompted"}            → prompted (only first time)
  {"event": "post_registration_skipped"}             → skipped
  {"event": "post_registration_completed"}           → completed (welcome tour done)
  {"event": "tour_completed", "tour": "<key>"}       → mark a contextual tour as seen
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import TourState

_EVENTS = {
    "post_registration_prompted": TourState.PostRegistration.PROMPTED,
    "post_registration_skipped": TourState.PostRegistration.SKIPPED,
    "post_registration_completed": TourState.PostRegistration.COMPLETED,
}


def _get_or_create(user):
    state, _ = TourState.objects.get_or_create(user=user)
    return state


class TourStateView(APIView):
    """GET /api/tour/"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        state = _get_or_create(request.user)
        return Response(
            {
                "success": True,
                "data": {
                    "post_registration": state.post_registration,
                    "post_registration_prompted_at": state.post_registration_prompted_at,
                    "post_registration_answered_at": state.post_registration_answered_at,
                    "completed_tours": state.completed_tours,
                },
            }
        )


class TourRecordView(APIView):
    """POST /api/tour/record/"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        event = (request.data.get("event") or "").strip()
        state = _get_or_create(request.user)

        if event in _EVENTS:
            # Only ever prompt once – ignore later "prompted" events.
            if (
                event == "post_registration_prompted"
                and state.post_registration
                != TourState.PostRegistration.NONE
            ):
                pass
            else:
                state.mark_post_registration(_EVENTS[event])
            return Response({"success": True, "data": {"event": event}})

        if event == "tour_completed":
            tour = (request.data.get("tour") or "").strip()
            if not tour:
                return Response(
                    {"success": False, "error": {"message": "tour is required."}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            state.complete_tour(tour)
            return Response({"success": True, "data": {"event": event, "tour": tour}})

        return Response(
            {"success": False, "error": {"message": f"Unknown event '{event}'."}},
            status=status.HTTP_400_BAD_REQUEST,
        )