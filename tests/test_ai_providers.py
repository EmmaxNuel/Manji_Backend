"""
Tests for the Manji AI provider abstraction (Phase 4): Gemini, OpenRouter,
and the automatic fallback chain between providers.
"""

import unittest.mock as mock

from django.test import TestCase, override_settings

from apps.ai.providers import (
    ChatResult,
    FallbackChatProvider,
    GeminiChatProvider,
    OpenRouterChatProvider,
    get_chat_provider,
)
from apps.stories.ai_service import AIError


def _gemini_response(text="Hello from Gemini.", tokens=12):
    return {
        "candidates": [{"content": {"parts": [{"text": text}]}}],
        "usageMetadata": {"totalTokenCount": tokens},
    }


class GeminiProviderTests(TestCase):
    def test_parses_generate_content_response(self):
        with mock.patch(
            "apps.ai.providers.requests.post"
        ) as post, override_settings(GEMINI_API_KEY="test-key"):
            post.return_value.status_code = 200
            post.return_value.json.return_value = _gemini_response()

            provider = GeminiChatProvider()
            result = provider.complete(
                [{"role": "user", "content": "Hi"}], max_tokens=100
            )

            self.assertEqual(result.content, "Hello from Gemini.")
            self.assertEqual(result.tokens_used, 12)

            url = post.call_args[0][0]
            self.assertIn("generateContent", url)
            self.assertIn("key=test-key", url)
            body = post.call_args[1]["json"]
            self.assertEqual(body["contents"][0]["role"], "user")
            self.assertEqual(body["generationConfig"]["maxOutputTokens"], 100)

    def test_roles_are_converted_to_gemini_shape(self):
        with mock.patch(
            "apps.ai.providers.requests.post"
        ) as post, override_settings(GEMINI_API_KEY="test-key"):
            post.return_value.status_code = 200
            post.return_value.json.return_value = _gemini_response()

            provider = GeminiChatProvider()
            provider.complete(
                [
                    {"role": "system", "content": "You are Manji AI."},
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there"},
                    {"role": "user", "content": "More"},
                ]
            )

            body = post.call_args[1]["json"]
            self.assertEqual(
                body["systemInstruction"]["parts"][0]["text"], "You are Manji AI."
            )
            roles = [c["role"] for c in body["contents"]]
            self.assertEqual(roles, ["user", "model", "user"])

    def test_missing_key_raises_ai_error(self):
        with override_settings(GEMINI_API_KEY=""):
            provider = GeminiChatProvider()
            with self.assertRaises(AIError):
                provider.complete([{"role": "user", "content": "Hi"}])

    def test_http_error_is_reported(self):
        with mock.patch(
            "apps.ai.providers.requests.post"
        ) as post, override_settings(GEMINI_API_KEY="test-key"):
            post.return_value.status_code = 500
            post.return_value.text = "boom"
            post.return_value.json.return_value = {}

            provider = GeminiChatProvider()
            with self.assertRaises(AIError):
                provider.complete([{"role": "user", "content": "Hi"}])

    def test_blocked_candidate_is_reported(self):
        with mock.patch(
            "apps.ai.providers.requests.post"
        ) as post, override_settings(GEMINI_API_KEY="test-key"):
            post.return_value.status_code = 200
            post.return_value.json.return_value = {"promptFeedback": {"blockReason": "SAFETY"}}

            provider = GeminiChatProvider()
            with self.assertRaises(AIError):
                provider.complete([{"role": "user", "content": "Hi"}])

    def test_empty_candidates_are_reported(self):
        with mock.patch(
            "apps.ai.providers.requests.post"
        ) as post, override_settings(GEMINI_API_KEY="test-key"):
            post.return_value.status_code = 200
            post.return_value.json.return_value = {"candidates": []}

            provider = GeminiChatProvider()
            with self.assertRaises(AIError):
                provider.complete([{"role": "user", "content": "Hi"}])


class OpenRouterProviderTests(TestCase):
    def test_uses_openrouter_base_and_key(self):
        with mock.patch(
            "apps.ai.providers.requests.post"
        ) as post, override_settings(
            OPENROUTER_API_KEY="or-key", AI_OPENROUTER_MODEL="model/a"
        ):
            post.return_value.status_code = 200
            post.return_value.json.return_value = {
                "choices": [{"message": {"content": "A reply."}}],
                "usage": {"total_tokens": 7},
            }

            provider = OpenRouterChatProvider()
            result = provider.complete([{"role": "user", "content": "Hi"}])

            self.assertEqual(result.content, "A reply.")
            self.assertEqual(result.tokens_used, 7)
            url = post.call_args[0][0]
            self.assertIn("openrouter.ai/api/v1/chat/completions", url)
            self.assertEqual(
                post.call_args[1]["headers"]["Authorization"], "Bearer or-key"
            )

    def test_missing_key_raises_ai_error(self):
        with override_settings(OPENROUTER_API_KEY=""):
            provider = OpenRouterChatProvider()
            with self.assertRaises(AIError):
                provider.complete([{"role": "user", "content": "Hi"}])


class _OkProvider:
    name = "primary"
    model = "primary-model"

    def complete(self, messages, max_tokens=800, temperature=0.7):
        return ChatResult("primary answer", self.model, tokens_used=1)


class _BrokenProvider:
    name = "broken"
    model = "broken-model"

    def complete(self, messages, max_tokens=800, temperature=0.7):
        raise AIError("Primary provider is down.")


class FallbackProviderTests(TestCase):
    def test_uses_primary_when_it_succeeds(self):
        fallback = FallbackChatProvider(_OkProvider(), _BrokenProvider())
        result = fallback.complete([{"role": "user", "content": "Hi"}])
        self.assertEqual(result.content, "primary answer")
        self.assertEqual(fallback.last_provider.name, "primary")

    def test_falls_back_to_secondary_when_primary_fails(self):
        fallback = FallbackChatProvider(_BrokenProvider(), _OkProvider())
        result = fallback.complete([{"role": "user", "content": "Hi"}])
        self.assertEqual(result.content, "primary answer")
        self.assertEqual(fallback.last_provider.name, "primary")

    def test_failure_of_both_propagates(self):
        fallback = FallbackChatProvider(_BrokenProvider(), _BrokenProvider())
        with self.assertRaises(AIError):
            fallback.complete([{"role": "user", "content": "Hi"}])


class GetChatProviderTests(TestCase):
    def test_returns_plain_provider_without_fallback(self):
        with override_settings(AI_CHAT_PROVIDER="gemini", AI_CHAT_FALLBACK_PROVIDER=""):
            provider = get_chat_provider()
            self.assertIsInstance(provider, GeminiChatProvider)

    def test_returns_fallback_wrapper_when_configured(self):
        with override_settings(
            AI_CHAT_PROVIDER="gemini", AI_CHAT_FALLBACK_PROVIDER="openrouter"
        ):
            provider = get_chat_provider()
            self.assertIsInstance(provider, FallbackChatProvider)
            self.assertIsInstance(provider.primary, GeminiChatProvider)
            self.assertIsInstance(provider.fallback, OpenRouterChatProvider)

    def test_ignores_fallback_that_matches_primary(self):
        with override_settings(
            AI_CHAT_PROVIDER="openrouter", AI_CHAT_FALLBACK_PROVIDER="openrouter"
        ):
            provider = get_chat_provider()
            self.assertIsInstance(provider, OpenRouterChatProvider)

    def test_unknown_provider_raises_ai_error(self):
        with override_settings(AI_CHAT_PROVIDER="nope", AI_CHAT_FALLBACK_PROVIDER=""):
            with self.assertRaises(AIError):
                get_chat_provider()