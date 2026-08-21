# Manji Backend

Django + Django REST Framework API for the **Manji** storytelling platform.
Handles authentication, stories, chapters, reading progress, the library,
AI generation, creator analytics, and discovery.

## Stack

- Python 3.12 · Django · Django REST Framework · SimpleJWT
- SQLite by default (`DATABASE_URL`), PostgreSQL-ready
- `django-environ` for `.env` configuration
- `drf-spectacular` (Swagger / ReDoc / OpenAPI), `django-filter`, CORS
- Pillow for the dev image-placeholder renderer

## Project layout

```
apps/
├── core/          pagination, permissions, exception handler
├── users/         custom User (reader/creator/admin), profiles, follows, auth views
├── stories/       Story, Genre, Tag, likes/bookmarks/follows, views, AI service
├── chapters/      Chapter, auto-numbering, images, reading progress
├── library/       currently reading, bookmarks, following, completed, history
├── social/        social features
├── notifications/
└── moderation/
config/settings/   base.py · dev.py · prod.py
tests/             pytest-style APITestCase suite (factories in tests/factories.py)
```

`manage.py` defaults to `config.settings.dev`.

## Setup & run

See [`../RUN.md`](../RUN.md) for full instructions. In short:

```bash
cp .env.example .env                       # edit SECRET_KEY, AI keys
./venv/bin/pip install -r requirements/dev.txt
./venv/bin/python manage.py migrate
./venv/bin/python manage.py seed_genres    # optional, first run
./venv/bin/python manage.py runserver 8000
```

Seed the official **MANJI** welcome story (free, 10 chapters, owned by the
official `Manji` account with generated cover/avatar):

```bash
./venv/bin/python manage.py seed_manji_story
```

It is idempotent: re-running updates the story and its chapters. The story is
`is_official=True` and is protected so normal users cannot edit or delete it.

## Environment variables

All settings live in `config/settings/base.py` and are read from
`Backend/Manji_Backend/.env` (see `.env.example`).

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Django secret (never commit a real one) |
| `DEBUG` | `True` in development |
| `ALLOWED_HOSTS` | Comma-separated hosts |
| `DATABASE_URL` | e.g. `sqlite:///db.sqlite3` (default) or `postgres://…` |
| `CORS_ALLOWED_ORIGINS` | Origins allowed for the React dev server |
| `EMAIL_BACKEND` | Console backend in development |
| `AI_OPENAI_API_KEY` / `AI_OPENAI_IMAGE_MODEL` | DALL-E image generation |
| `AI_STABILITY_API_KEY` | Stability AI image generation |
| `AI_LEONARDO_API_KEY` | Leonardo image generation |
| `AI_IMAGE_PROVIDER_DEFAULT` | Default image provider: `dalle`, `stability`, `leonardo`, `local` |
| `AI_TEXT_API_KEY` | LLM key for text generation (OpenAI-compatible) |
| `AI_TEXT_BASE_URL` | e.g. `https://api.openai.com/v1` or a local Ollama `http://localhost:11434/v1` |
| `AI_TEXT_MODEL` | e.g. `gpt-4o-mini`, `llama3` |
| `AI_CHAT_PROVIDER` | Manji AI chat provider (`openai` = any OpenAI-compatible endpoint) |
| `AI_CHAT_MODEL` | Optional; falls back to `AI_TEXT_MODEL` |
| `AI_CHAT_MAX_TOKENS` | Max tokens per chat reply (default `800`) |
| `AI_CHAT_HISTORY_MESSAGES` | Previous turns included as context (default `12`) |
| `AI_CHAT_CONTEXT_MAX_CHARS` | Max draft chars sent to the model (default `8000`) |
| `AI_ALLOW_LOCAL_PLACEHOLDER` | Dev-only local Pillow placeholder renderer |
| `AI_IMAGE_QUOTA_DAILY` | Per-user daily image generation limit |
| `AI_TEXT_QUOTA_DAILY` | Per-user daily text generation limit |

AI keys are **never** committed; leave them empty to fall back to the local
placeholder in development.

## Tests

```bash
./venv/bin/python manage.py test
```

The suite covers auth, users, chapters (auto-numbering + publish flow),
and AI endpoints. Test data uses Factory Boy factories in `tests/factories.py`.

## Key API endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/auth/register/` · `/api/auth/login/` · `/api/auth/refresh/` | Auth (JWT) |
| `GET/PATCH` | `/api/users/me/` | Current user + profile |
| `GET` | `/api/users/<username>/` | Public profile |
| `POST` | `/api/users/<username>/follow/` | Follow / unfollow |
| `GET` | `/api/users/creators/` | Creator spotlights (home feed) |
| `GET/POST` | `/api/stories/` | List / create stories |
| `GET/PATCH/DELETE` | `/api/stories/<slug>/` | Story detail / update / delete |
| `POST` | `/api/stories/<slug>/publish/` · `/unpublish/` | Publish workflow |
| `POST` | `/api/stories/<slug>/like/` · `/bookmark/` · `/follow/` | Engagement |
| `GET` | `/api/stories/recommended/` | Personalized recommendations |
| `GET` | `/api/stories/mine/` | Creator's own stories |
| `GET` | `/api/stories/mine/stats/` | Aggregated creator stats |
| `GET` | `/api/stories/mine/analytics/` | 14-day series + per-story breakdown |
| `GET/POST` | `/api/stories/<slug>/chapters/` | List / create chapters |
| `GET/PATCH/DELETE` | `/api/chapters/<uuid>/` | Chapter detail / update / delete |
| `POST/GET` | `/api/chapters/reading/progress/` | Save / fetch reading progress |
| `GET` | `/api/library/reading/` · `/bookmarks/` · `/following/` · `/completed/` · `/history/` | Library lists |
| `POST` | `/api/ai/images/generate/` | Start image generation |
| `GET` | `/api/ai/generations/` · `/api/ai/images/` | Generation jobs / image gallery |
| `POST` | `/api/ai/images/<id>/apply/` | Apply image to cover or chapter |
| `POST` | `/api/ai/ideas/` · `/api/ai/titles/` · `/api/ai/outline/` | Text generation |
| `GET` | `/api/ai/usage/` | AI quota + usage summary |
| `POST` | `/api/ai/chat/` | Manji AI chat turn (story-scoped, conversation history) |
| `GET/DELETE` | `/api/ai/conversations/<id>/` | Conversation detail / delete |
| `GET` | `/api/stories/<id>/ai/context/` | Story context snapshot for Manji AI |
| `GET` | `/api/stories/<id>/ai/conversations/` | A story's AI conversations |

Interactive docs: `http://localhost:8000/api/docs/` (Swagger),
`http://localhost:8000/api/redoc/` (ReDoc).