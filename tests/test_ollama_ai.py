"""Ollama provider tests without a live model."""
import json
import os
import unittest
from unittest.mock import patch

from flask import Flask

import tests
from app.services.ai_service import (
    FallbackAIProvider,
    OllamaAIProvider,
    get_ai_provider,
)
from app.services.assistant_service import process_assistant_chat


class OllamaProviderTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            AI_PROVIDER="ollama",
            AI_API_KEY="",
            OLLAMA_BASE_URL="http://127.0.0.1:11434",
            OLLAMA_MODEL="llama3.1:latest",
            OLLAMA_TIMEOUT_SECONDS="10",
        )
        self.ctx = self.app.test_request_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_factory_selects_ollama_without_api_key(self):
        provider = get_ai_provider()

        self.assertIsInstance(provider, OllamaAIProvider)
        self.assertEqual(provider.model, "llama3.1:latest")

    def test_ollama_response_through_assistant(self):
        result_body = {
            "message": {
                "role": "assistant",
                "content": "Halo, saya asisten SehatWarga.",
            },
            "done": True,
        }

        with patch("urllib.request.urlopen") as http:
            response = http.return_value.__enter__.return_value
            response.read.return_value = json.dumps(
                result_body
            ).encode("utf-8")

            result, status = process_assistant_chat("Halo")

        self.assertEqual(status, 200)
        self.assertEqual(
            result["message"],
            "Halo, saya asisten SehatWarga.",
        )
        http.assert_called_once()

        request = http.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))

        self.assertEqual(payload["model"], "llama3.1:latest")
        self.assertFalse(payload["stream"])

    def test_network_failure_uses_local_fallback(self):
        with patch(
            "urllib.request.urlopen",
            side_effect=TimeoutError("test timeout"),
        ) as http:
            result, status = process_assistant_chat("Halo")

        self.assertEqual(status, 200)
        self.assertEqual(
            result["message"],
            FallbackAIProvider().generate_response(
                "Halo", "GREETING"
            ),
        )
        http.assert_called_once()

    def test_facility_search_does_not_call_ollama(self):
        with (
            patch("urllib.request.urlopen") as http,
            patch(
                "app.services.assistant_service.search_facilities",
                return_value=[],
            ) as search,
        ):
            result, status = process_assistant_chat(
                "Cari klinik di Surabaya"
            )

        self.assertEqual(status, 200)
        self.assertEqual(result["intent"], "FACILITY_SEARCH")
        search.assert_called()
        http.assert_not_called()

if __name__ == "__main__":
    unittest.main()