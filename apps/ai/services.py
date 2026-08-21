"""
Manji AI orchestration.

Responsibilities:
- Build a compact, relevant story context snapshot (never the whole novel).
- Run a lightweight safety guardrail before every chat turn.
- Enforce the per-user daily text quota and log every call into AIUsageLog.
- Persist AIRequest / AIResponse audit records alongside the conversation.
"""

import json

from django.conf import settings

from apps.chapters.models import Chapter
from apps.stories.ai_service import AIError, check_text_quota, log_usage

from .models import AIMessage, AIConversation, AIRequest, AIResponse
from .providers import get_chat_provider

SYSTEM_PROMPT = (
    "You are Manji AI, the creative co-author and writing assistant built into "
    "Manji, a platform for novels, short stories, comics, manga and manhua.\n\n"
    "You help the creator develop their story: brainstorming directions, "
    "continuing drafts, characters, world building, plot, structure and "
    "rewriting. Always respect the creator's voice and intended meaning. Never "
    "invent facts that contradict the story context below; if the draft is "
    "thin, say so and ask a clarifying question. Keep answers focused, "
    "practical and useful for a working writer.\n\n"
    "Refuse requests that are illegal, abusive or dangerous, and do not help "
    "produce harmful content.\n\n"
    "STORY CONTEXT:\n{context}"
)

PROJECT_SYSTEM_PROMPT = (
    "You are Manji AI, the creative co-author built into MANJI STUDIO, a "
    "production workspace for comics, manga, manhua, webtoons and novels.\n\n"
    "You help the creator develop the whole production: story structure, "
    "character design, scene blocking, dialogue, pacing, art direction and "
    "visual consistency. Treat the project context below (project type, art "
    "direction, linked story, cast and scene board) as the ground truth. Never "
    "invent characters, scenes or facts that contradict it; if the context is "
    "thin, say so and ask a clarifying question. When suggesting visuals, "
    "always stay consistent with the project's art direction.\n\n"
    "Refuse requests that are illegal, abusive or dangerous, and do not help "
    "produce harmful content.\n\n"
    "PROJECT CONTEXT:\n{context}"
)

# Lightweight Phase-1 guardrail. Provider-side content filters still apply and
# this list is expected to grow (and move to moderation tooling) in later phases.
_BLOCKED_TERMS = (
    "child porn",
    "sexual exploitation of minors",
    "instruction manual for a weapon",
    "how to build a bomb",
    "make illegal drugs",
    "assassination instructions",
    "write something illegal",
    "write something clearly illegal",
    "illegal content",
    "how to commit a crime",
)


def _blocked(text):
    lowered = (text or "").lower()
    return any(term in lowered for term in _BLOCKED_TERMS)


def _truncate(text, limit):
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + " …"


def _chapters_summary(story):
    rows = []
    for chapter in story.chapters.order_by("chapter_number")[:50]:
        rows.append(
            {
                "number": chapter.chapter_number,
                "title": chapter.title,
                "status": chapter.status,
                "word_count": chapter.word_count,
                "summary": _truncate(chapter.ai_summary, 200),
            }
        )
    return rows


def build_story_context(story, chapter=None):
    """Assemble a compact, relevant snapshot of the story for the model."""
    context = {
        "title": story.title,
        "description": story.description or "",
        "genres": [g.name for g in story.genres.all()],
        "content_type": story.content_type,
        "status": story.status,
        "word_count": story.word_count,
        "chapters": _chapters_summary(story),
    }
    if chapter is not None:
        context["current_chapter"] = {
            "number": chapter.chapter_number,
            "title": chapter.title,
            "content": _truncate(
                chapter.content or "", settings.AI_CHAT_CONTEXT_MAX_CHARS
            ),
        }
    return context


def _characters_summary(project, limit=30):
    rows = []
    for character in project.characters.order_by("order", "name")[:limit]:
        rows.append(
            {
                "name": character.name,
                "role": character.role,
                "age": character.age,
                "appearance": _truncate(character.appearance, 180),
                "personality": _truncate(character.personality, 180),
            }
        )
    return rows


def _scenes_summary(project, limit=60):
    rows = []
    for scene in project.scenes.order_by("order", "created_at")[:limit]:
        rows.append(
            {
                "order": scene.order,
                "title": scene.title,
                "location": scene.location,
                "mood": scene.mood,
                "characters": scene.characters,
                "summary": _truncate(scene.description, 160),
            }
        )
    return rows


def build_project_context(project, scene=None):
    """Assemble a project-scoped snapshot for the co-author model.

    The snapshot combines the project's identity and art direction with its
    linked story, its cast and its scene board, so the AI can reason about the
    whole production, not just the prose.
    """
    story = project.story
    context = {
        "title": project.title,
        "project_type": project.project_type,
        "status": project.status,
        "description": project.description or "",
        "art_style": _truncate(project.get_art_style_context(), 400),
        "story": None,
        "characters": _characters_summary(project),
        "scenes": _scenes_summary(project),
    }
    if story is not None:
        context["story"] = {
            "title": story.title,
            "description": story.description or "",
            "genres": [g.name for g in story.genres.all()],
            "word_count": story.word_count,
            "chapters": _chapters_summary(story),
        }
    if scene is not None:
        context["current_scene"] = {
            "order": scene.order,
            "title": scene.title,
            "location": scene.location,
            "mood": scene.mood,
            "characters": scene.characters,
            "description": _truncate(scene.description, 240),
            "dialogue": _truncate(scene.dialogue, settings.AI_CHAT_CONTEXT_MAX_CHARS),
            "narration": _truncate(scene.narration, settings.AI_CHAT_CONTEXT_MAX_CHARS),
        }
    return context


def _format_context_block(context):
    lines = [
        f"- Title: {context['title']}",
        f"- Content type: {context['content_type']}",
        f"- Status: {context['status']}",
        f"- Description: {context['description']}",
        f"- Genres: {', '.join(context['genres']) or 'none'}",
    ]
    if context.get("word_count"):
        lines.append(f"- Total words: {context['word_count']}")
    if context["chapters"]:
        lines.append("- Chapters:")
        for ch in context["chapters"]:
            summary = f" – {ch['summary']}" if ch["summary"] else ""
            lines.append(f"  * #{ch['number']} {ch['title']} ({ch['status']}){summary}")
    if context.get("current_chapter"):
        cur = context["current_chapter"]
        lines.append(f"- Current chapter #{cur['number']}: {cur['title']}")
        lines.append(f"  Current draft:\n{cur['content']}")
    return "\n".join(lines)


def _format_project_context_block(context):
    lines = [
        f"- Title: {context['title']}",
        f"- Project type: {context['project_type']}",
        f"- Status: {context['status']}",
        f"- Description: {context['description']}",
    ]
    if context.get("art_style"):
        lines.append(f"- Art direction: {context['art_style']}")
    if context.get("story"):
        story = context["story"]
        lines.append(
            f"- Linked story: {story['title']} "
            f"({', '.join(story['genres']) or 'no genres'}, "
            f"{story['word_count']} words)"
        )
        lines.append(f"  Synopsis: {story['description']}")
        if story["chapters"]:
            lines.append("  Chapters:")
            for ch in story["chapters"]:
                summary = f" – {ch['summary']}" if ch["summary"] else ""
                lines.append(f"    * #{ch['number']} {ch['title']} ({ch['status']}){summary}")
    if context["characters"]:
        lines.append("- Cast:")
        for ch in context["characters"]:
            details = []
            if ch["role"]:
                details.append(ch["role"])
            if ch["age"]:
                details.append(f"{ch['age']} years")
            suffix = f" ({', '.join(details)})" if details else ""
            lines.append(f"  * {ch['name']}{suffix}")
            if ch["appearance"]:
                lines.append(f"    Looks: {ch['appearance']}")
            if ch["personality"]:
                lines.append(f"    Personality: {ch['personality']}")
    if context["scenes"]:
        lines.append("- Scene board:")
        for sc in context["scenes"]:
            cast = ", ".join(sc["characters"] or []) or "no characters"
            lines.append(
                f"  * #{sc['order']} {sc['title']} "
                f"[{sc['location'] or 'no location'}"
                f"{' · ' + sc['mood'] if sc['mood'] else ''}] — {cast}"
            )
            if sc["summary"]:
                lines.append(f"    {sc['summary']}")
    if context.get("current_scene"):
        cur = context["current_scene"]
        lines.append(f"- Current scene #{cur['order']}: {cur['title']}")
        if cur["location"]:
            lines.append(f"  Location: {cur['location']}")
        if cur["mood"]:
            lines.append(f"  Mood: {cur['mood']}")
        if cur["characters"]:
            lines.append(f"  Characters: {', '.join(cur['characters'])}")
        if cur["description"]:
            lines.append(f"  Description: {cur['description']}")
        if cur["dialogue"]:
            lines.append(f"  Dialogue so far:\n{cur['dialogue']}")
        if cur["narration"]:
            lines.append(f"  Narration so far:\n{cur['narration']}")
    return "\n".join(lines)


def _history_messages(conversation):
    """Return the recent turns as an OpenAI-style message list."""
    messages = list(conversation.messages.all())
    recent = messages[-settings.AI_CHAT_HISTORY_MESSAGES:]
    return [
        {"role": message.role, "content": message.content}
        for message in recent
        if message.role in (AIMessage.Role.USER, AIMessage.Role.ASSISTANT)
    ]


def run_chat(user, message, conversation, story=None, project=None, chapter=None, scene=None):
    """
    Perform one Manji AI chat turn inside an existing conversation.

    The turn is scoped to either a story (legacy studio flow) or a project
    (MANJI STUDIO workspace). A project turn pulls in the project's art
    direction, cast and scene board as context.

    Returns (assistant_message, conversation). Raises AIError for quota
    violations, guardrail hits, or provider failures.
    """
    if _blocked(message):
        raise AIError(
            "That request isn't supported by Manji AI. Keep the conversation "
            "focused on your story."
        )

    check_text_quota(user)

    if project is not None:
        context = build_project_context(project, scene)
        prompt = PROJECT_SYSTEM_PROMPT.format(context=_format_project_context_block(context))
    else:
        context = build_story_context(story, chapter)
        prompt = SYSTEM_PROMPT.format(context=_format_context_block(context))

    messages = [{"role": "system", "content": prompt}]
    messages.extend(_history_messages(conversation))
    messages.append({"role": "user", "content": message})

    provider = get_chat_provider()

    ai_request = AIRequest.objects.create(
        user=user,
        project=project,
        story=story,
        conversation=conversation,
        action="ai_chat",
        provider=provider.name,
        model=provider.model,
        prompt=json.dumps(messages, ensure_ascii=False)[:20000],
    )

    AIMessage.objects.create(
        conversation=conversation,
        role=AIMessage.Role.USER,
        content=message,
        context=context,
    )

    try:
        result = provider.complete(
            messages,
            max_tokens=settings.AI_CHAT_MAX_TOKENS,
            temperature=0.7,
        )
    except AIError as exc:
        ai_request.status = AIRequest.Status.FAILED
        ai_request.error_message = str(exc)[:2000]
        ai_request.save(update_fields=["status", "error_message"])
        log_usage(
            user, "ai_chat", provider.name, provider.model, success=False,
            error_message=str(exc)[:2000], story=story, project=project,
            request_data={"message": message[:500]},
        )
        raise

    # A fallback chain may have served the turn from a different provider.
    used = getattr(provider, "last_provider", None) or provider
    ai_request.provider = used.name
    ai_request.model = used.model
    ai_request.status = AIRequest.Status.SUCCESS
    ai_request.tokens_used = result.tokens_used
    ai_request.processing_time = result.processing_time
    ai_request.save(update_fields=["provider", "model", "status", "tokens_used", "processing_time"])

    AIResponse.objects.create(
        request=ai_request,
        content=result.content,
        model=result.model,
        tokens_used=result.tokens_used,
        processing_time=result.processing_time,
    )

    assistant_message = AIMessage.objects.create(
        conversation=conversation,
        role=AIMessage.Role.ASSISTANT,
        content=result.content,
        tokens_used=result.tokens_used,
    )

    log_usage(
        user, "ai_chat", used.name, used.model,
        processing_time=result.processing_time, story=story, project=project,
        request_data={"message": message[:500]},
        response_data={"tokens": result.tokens_used},
    )

    conversation.save(update_fields=["updated_at"])

    return assistant_message, conversation


def new_conversation(user, first_message, story=None, project=None):
    return AIConversation.objects.create(
        user=user,
        story=story,
        project=project,
        title=_truncate(first_message, 60),
    )