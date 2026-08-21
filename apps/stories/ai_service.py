"""
AI service layer for Manji.

Responsibilities:
- Generate images via pluggable providers (DALL-E, Stability, Leonardo, local).
- Generate text ideas/titles/outlines via any OpenAI-compatible chat endpoint.
- Enforce per-user daily quotas and log every call into ``AIUsageLog``.
- Run image generation asynchronously in a background thread.

Architecture decision: providers are resolved behind a single ``generate_image``
function so the API layer never talks to a provider directly. Providers raise
``AIError`` with a human readable message which the API layer turns into a 400.
"""

import base64
import io
import json
import logging
import random
import threading
import time
from datetime import timedelta

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import close_old_connections, transaction
from django.utils import timezone
from PIL import Image, ImageDraw

from apps.chapters.models import AIImageGeneration
from .models import AIGeneratedImage, AIUsageLog

logger = logging.getLogger(__name__)

TIMEOUT = 60  # seconds, per HTTP call

TEXT_ACTIONS = ("generate_idea", "generate_titles", "generate_outline", "ai_chat")

# Provider key used by the API layer; "stable_diffusion" is kept as an alias
# for the Stability provider for backwards compatibility.
PROVIDER_ALIASES = {"stable_diffusion": "stability"}


class AIError(Exception):
    """Raised when a provider is unavailable or the request fails."""


# ---------------------------------------------------------------------------
# Quotas & usage logging
# ---------------------------------------------------------------------------

def check_image_quota(user):
    limit = settings.AI_IMAGE_QUOTA_DAILY
    today = timezone.localdate()
    used = AIImageGeneration.objects.filter(user=user, created_at__date=today).count()
    if used >= limit:
        raise AIError(
            f"Daily image generation limit reached ({used}/{limit}). "
            "Try again tomorrow."
        )


def check_text_quota(user):
    limit = settings.AI_TEXT_QUOTA_DAILY
    today = timezone.localdate()
    used = AIUsageLog.objects.filter(
        user=user, action__in=TEXT_ACTIONS, created_at__date=today
    ).count()
    if used >= limit:
        raise AIError(
            f"Daily AI writing limit reached ({used}/{limit}). Try again tomorrow."
        )


def log_usage(user, action, provider, model="", cost=None, processing_time=None,
              success=True, error_message="", request_data=None, response_data=None,
              story=None, project=None):
    """Record an AI call into AIUsageLog. Never raises."""
    try:
        AIUsageLog.objects.create(
            user=user,
            story=story,
            project=project,
            action=action,
            provider=provider,
            model=model,
            cost=cost or 0,
            processing_time=processing_time,
            success=success,
            error_message=error_message[:2000],
            request_data=request_data or {},
            response_data=response_data or {},
        )
    except Exception:  # pragma: no cover - logging must never break the flow
        logger.exception("Failed to write AI usage log")


def _resolve_provider(name):
    name = (name or settings.AI_IMAGE_PROVIDER_DEFAULT).lower()
    return PROVIDER_ALIASES.get(name, name)


def _download_bytes(url):
    resp = requests.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.content


# ---------------------------------------------------------------------------
# Image providers
# ---------------------------------------------------------------------------

def _generate_dalle(gen):
    """DALL-E 3 via the OpenAI Images API (base64 output)."""
    if not settings.AI_OPENAI_API_KEY:
        raise AIError(
            "OpenAI image generation is not configured. Set AI_OPENAI_API_KEY "
            "in the backend .env file."
        )
    # DALL-E 3 only supports three sizes; pick the best fit for the aspect ratio.
    if gen.width > gen.height * 1.2:
        size = "1792x1024"
    elif gen.height > gen.width * 1.2:
        size = "1024x1792"
    else:
        size = "1024x1024"

    start = time.monotonic()
    resp = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {settings.AI_OPENAI_API_KEY}"},
        json={
            "model": settings.AI_OPENAI_IMAGE_MODEL,
            "prompt": gen.prompt,
            "n": 1,
            "size": size,
            "response_format": "b64_json",
        },
        timeout=TIMEOUT,
    )
    processing_time = time.monotonic() - start
    if resp.status_code != 200:
        detail = resp.json().get("error", {}).get("message", resp.text)[:500]
        raise AIError(f"OpenAI image API error: {detail}")

    payload = resp.json()["data"][0]
    raw = base64.b64decode(payload["b64_json"]) if "b64_json" in payload else _download_bytes(payload["url"])
    width, height = size.split("x")
    return raw, "png", int(width), int(height), settings.AI_OPENAI_IMAGE_MODEL, processing_time


def _generate_stability(gen):
    """Stability AI text-to-image (v2beta endpoint, PNG bytes)."""
    if not settings.AI_STABILITY_API_KEY:
        raise AIError(
            "Stability AI is not configured. Set AI_STABILITY_API_KEY in the "
            "backend .env file."
        )
    aspect = "1:1"
    if gen.width > gen.height * 1.2:
        aspect = "16:9"
    elif gen.height > gen.width * 1.2:
        aspect = "9:16"

    start = time.monotonic()
    resp = requests.post(
        "https://api.stability.ai/v2beta/stable-image/generate/text-to-image",
        headers={
            "Authorization": f"Bearer {settings.AI_STABILITY_API_KEY}",
            "Accept": "image/*",
        },
        files={"none": ""},
        data={
            "prompt": gen.prompt,
            "negative_prompt": gen.negative_prompt,
            "aspect_ratio": aspect,
            "output_format": "png",
            "seed": gen.seed or random.randint(0, 2**32 - 1),
        },
        timeout=TIMEOUT,
    )
    processing_time = time.monotonic() - start
    if resp.status_code != 200:
        detail = ""
        try:
            detail = resp.json().get("message", resp.text)
        except ValueError:
            detail = resp.text
        raise AIError(f"Stability AI error: {detail[:500]}")

    width = gen.width if gen.width <= 1536 else 1536
    height = gen.height if gen.height <= 1536 else 1536
    return resp.content, "png", width, height, "stable-image-xl", processing_time


def _generate_leonardo(gen):
    """Leonardo.ai generations API: create then poll until the image is ready."""
    if not settings.AI_LEONARDO_API_KEY:
        raise AIError(
            "Leonardo AI is not configured. Set AI_LEONARDO_API_KEY in the "
            "backend .env file."
        )
    headers = {
        "Authorization": f"Bearer {settings.AI_LEONARDO_API_KEY}",
        "Accept": "application/json",
    }
    start = time.monotonic()
    create = requests.post(
        "https://cloud.leonardo.ai/api/rest/v1/generations",
        headers=headers,
        json={
            "prompt": gen.prompt,
            "negative_prompt": gen.negative_prompt,
            "width": gen.width,
            "height": gen.height,
            "num_images": 1,
            "seed": int(gen.seed) if str(gen.seed).isdigit() else 0,
        },
        timeout=TIMEOUT,
    )
    if create.status_code not in (200, 201):
        raise AIError(f"Leonardo API error: {create.text[:500]}")

    generation_id = create.json()["sdGenerationJob"]["generationId"]

    # Poll every 5s until COMPLETE / FAILED (max ~90s).
    deadline = time.monotonic() + 90
    image_url = None
    while time.monotonic() < deadline:
        time.sleep(5)
        status_resp = requests.get(
            f"https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}",
            headers=headers,
            timeout=TIMEOUT,
        )
        if status_resp.status_code != 200:
            continue
        data = status_resp.json().get("generations_by_pk", {})
        if data.get("status") == "COMPLETE":
            images = data.get("generated_images") or []
            if images:
                image_url = images[0].get("url")
                break
        elif data.get("status") in ("FAILED", "CANCELED"):
            raise AIError(f"Leonardo generation failed: {data.get('failureReason') or 'unknown'}")
    if not image_url:
        raise AIError("Leonardo generation timed out.")

    raw = _download_bytes(image_url)
    processing_time = time.monotonic() - start
    return raw, "png", gen.width, gen.height, "leonardo-xl", processing_time


def _generate_local(gen):
    """
    Development-only placeholder renderer (Pillow).

    Produces a real PNG gradient image labelled with the requested style so the
    full image pipeline (storage, gallery, cover application) can be exercised
    without an external API key. Gated behind ``AI_ALLOW_LOCAL_PLACEHOLDER`` and
    disabled in production settings.
    """
    if not settings.AI_ALLOW_LOCAL_PLACEHOLDER:
        raise AIError(
            "No image provider is configured (dalle/stability/leonardo). "
            "Set an API key in the backend .env file."
        )
    seed = gen.seed or str(random.randint(0, 99999))
    rng = random.Random(hash(gen.prompt + seed) % (2**32))
    w, h = gen.width, gen.height
    top = tuple(rng.randint(20, 235) for _ in range(3))
    bottom = tuple(rng.randint(20, 235) for _ in range(3))

    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (w, y)], fill=color)

    label = gen.style or "Manji AI"
    draw.text((16, 16), label, fill=(255, 255, 255))
    draw.text((16, h - 48), "AI placeholder", fill=(255, 255, 255))

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.read(), "png", w, h, "local-placeholder", 0.0


_IMAGE_PROVIDERS = {
    "dalle": _generate_dalle,
    "stability": _generate_stability,
    "leonardo": _generate_leonardo,
    "local": _generate_local,
}


def generate_image_bytes(gen):
    """Resolve provider and return (bytes, ext, width, height, model, seconds)."""
    provider = _resolve_provider(gen.provider)
    handler = _IMAGE_PROVIDERS.get(provider)
    if handler is None:
        raise AIError(
            f"Unknown image provider '{gen.provider}'. "
            "Supported: dalle, stability, leonardo, local."
        )
    return handler(gen)


# ---------------------------------------------------------------------------
# Async worker
# ---------------------------------------------------------------------------

def run_image_generation(gen_id):
    """
    Background worker: performs the actual provider call and stores the result.

    Runs in its own thread so it must close stale DB connections before
    touching the database (avoids lock issues, especially on SQLite).
    """
    close_old_connections()
    try:
        gen = AIImageGeneration.objects.get(id=gen_id)
    except AIImageGeneration.DoesNotExist:
        return

    gen.status = AIImageGeneration.Status.PROCESSING
    gen.save(update_fields=["status"])

    provider = _resolve_provider(gen.provider)
    try:
        raw, ext, width, height, model, processing_time = generate_image_bytes(gen)
        name = f"generations/{gen.story.id}/{gen.id}.{ext}"

        with transaction.atomic():
            gen.result_image.save(name, ContentFile(raw), save=False)
            gen.status = AIImageGeneration.Status.COMPLETED
            gen.generation_time = round(processing_time, 2)
            gen.completed_at = timezone.now()
            gen.save()

            # Expose the finished image as a usable asset in the story gallery.
            AIGeneratedImage.objects.create(
                story=gen.story,
                user=gen.user,
                prompt=gen.prompt,
                negative_prompt=gen.negative_prompt,
                style=gen.style,
                ai_provider=provider,
                image_type=gen.image_type or AIGeneratedImage.ImageType.COVER,
                image=gen.result_image,
                width=width,
                height=height,
                seed=gen.seed,
                model_version=model,
                generation_time=processing_time,
                cost=gen.cost,
                is_approved=True,
            )

        log_usage(
            gen.user, "generate_image", provider, model,
            cost=gen.cost, processing_time=processing_time, story=gen.story,
            request_data={"prompt": gen.prompt, "image_type": gen.image_type},
        )
        logger.info("AI image %s completed via %s", gen.id, provider)
    except (AIError, requests.RequestException, KeyError, ValueError) as exc:
        gen.status = AIImageGeneration.Status.FAILED
        gen.error_message = str(exc)[:2000]
        gen.completed_at = timezone.now()
        gen.save(update_fields=["status", "error_message", "completed_at"])
        log_usage(
            gen.user, "generate_image", provider, success=False,
            error_message=str(exc)[:2000], story=gen.story,
        )
        logger.warning("AI image %s failed: %s", gen.id, exc)


def start_generation_worker(gen_id):
    """
    Kick off the worker thread. Waits for the current DB transaction to commit
    so the background thread never contends with the request transaction.
    """
    def _spawn():
        threading.Thread(target=run_image_generation, args=(gen_id,), daemon=True).start()

    connection = transaction.get_connection()
    if connection.in_atomic_block:
        transaction.on_commit(_spawn)
    else:
        _spawn()


# ---------------------------------------------------------------------------
# Text / idea generation (OpenAI-compatible chat completions)
# ---------------------------------------------------------------------------

def _chat_completion(system, user, max_tokens=800, temperature=0.8):
    """Call an OpenAI-compatible chat completions endpoint.

    Retries up to 3 times because some models (e.g. reasoning models on free
    tiers) occasionally return a response with ``content=None``.
    """
    base_url = settings.AI_TEXT_BASE_URL.rstrip("/")
    api_key = settings.AI_TEXT_API_KEY
    model = settings.AI_TEXT_MODEL

    if not base_url or not model:
        raise AIError("AI_TEXT_BASE_URL / AI_TEXT_MODEL are not configured.")
    if api_key == "" and base_url.startswith("https://api.openai.com"):
        raise AIError(
            "Text generation is not configured. Set AI_TEXT_API_KEY in the "
            "backend .env file (or point AI_TEXT_BASE_URL at a local "
            "OpenAI-compatible server such as Ollama)."
        )

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    last_err = None
    for attempt in range(3):
        try:
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=TIMEOUT * 2,
            )
            if resp.status_code != 200:
                detail = resp.text[:500]
                last_err = AIError(f"Text generation API error ({resp.status_code}): {detail}")
                if resp.status_code in (401, 403, 402):
                    raise last_err
            else:
                data = resp.json()
                content = data["choices"][0]["message"].get("content")
                if content:
                    return content.strip()
                last_err = AIError("The AI returned an empty response. Please try again.")
        except AIError:
            raise
        except Exception as exc:  # network errors
            last_err = exc
        time.sleep(1.5 * (attempt + 1))

    raise last_err or AIError("AI text generation failed. Please try again.")


def _parse_json_response(text):
    """Extract a JSON object/array from an LLM response."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Strip markdown code fences.
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        text = text.removeprefix("json").strip()
        return json.loads(text)
    raise AIError("The AI returned malformed JSON. Please try again.")


_STORY_IDEA_SYSTEM = (
    "You are Manji's creative writing assistant. You help writers invent fresh, "
    "marketable stories for a platform that hosts novels, short stories, comics, "
    "manga and manhua. You respond only with valid JSON and nothing else."
)


def generate_story_ideas(user, genre=None, content_type=None, themes="", tone="",
                         count=5, language="en", story=None):
    """Return a list of story idea objects."""
    check_text_quota(user)
    start = time.monotonic()

    params = {
        "genre": genre or "any",
        "content_type": content_type or "novel",
        "themes": themes or "any",
        "tone": tone or "balanced",
        "count": max(1, min(count, 10)),
        "language": language,
    }
    user_prompt = (
        "Create {count} distinct story ideas for a {genre} {content_type}. "
        "Themes: {themes}. Tone: {tone}.\n"
        "Return a JSON array, each item with exactly these keys: "
        '"title", "genre", "premise" (2-3 sentence hook), "logline", '
        '"audience", "tags" (array of 3-6 tags).\n'
        "Write the content in language code '{language}' (use English for 'en')."
    ).format(**params)

    raw = _chat_completion(_STORY_IDEA_SYSTEM, user_prompt, max_tokens=1600)
    processing_time = time.monotonic() - start
    ideas = _parse_json_response(raw)

    if not isinstance(ideas, list):
        raise AIError("Expected a JSON array of story ideas.")

    log_usage(
        user, "generate_idea", "text", settings.AI_TEXT_MODEL,
        processing_time=processing_time, story=story,
        request_data=params,
    )
    return ideas


def generate_titles(user, premise, style="", count=8, language="en", story=None):
    """Return a list of title suggestions with a one-line rationale each."""
    check_text_quota(user)
    start = time.monotonic()
    count = max(1, min(count, 12))

    user_prompt = (
        "The premise of a story is: \"{premise}\"\n"
        "Style hint: {style}.\n"
        "Suggest {count} strong, marketable titles in language '{language}'.\n"
        "Return a JSON array of objects with exactly these keys: "
        '"title", "rationale" (why it works).'
    ).format(premise=premise[:1500], style=style or "any", count=count, language=language)

    raw = _chat_completion(_STORY_IDEA_SYSTEM, user_prompt, max_tokens=1000)
    processing_time = time.monotonic() - start
    titles = _parse_json_response(raw)
    if not isinstance(titles, list):
        raise AIError("Expected a JSON array of title suggestions.")

    log_usage(
        user, "generate_titles", "text", settings.AI_TEXT_MODEL,
        processing_time=processing_time, story=story,
    )
    return titles


def generate_chapter_outline(user, premise, chapter_count=8, language="en", story=None):
    """Return a chapter-by-chapter outline for a story."""
    check_text_quota(user)
    start = time.monotonic()
    chapter_count = max(1, min(chapter_count, 60))

    user_prompt = (
        "Story premise: \"{premise}\"\n"
        "Create a {count}-chapter outline in language '{language}'.\n"
        "Return a JSON array of objects with exactly these keys: "
        '"number", "title", "summary" (1-2 sentences).'
    ).format(premise=premise[:1500], count=chapter_count, language=language)

    raw = _chat_completion(_STORY_IDEA_SYSTEM, user_prompt, max_tokens=2400)
    processing_time = time.monotonic() - start
    outline = _parse_json_response(raw)
    if not isinstance(outline, list):
        raise AIError("Expected a JSON array of chapter outlines.")

    log_usage(
        user, "generate_outline", "text", settings.AI_TEXT_MODEL,
        processing_time=processing_time, story=story,
    )
    return outline
