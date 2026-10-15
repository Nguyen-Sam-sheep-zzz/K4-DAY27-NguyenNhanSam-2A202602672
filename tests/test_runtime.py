import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from common.llm import get_llm
from exercises.runtime import load_runtime_env


class RuntimeConfigurationTests(unittest.TestCase):
    def test_explicit_local_provider_key_takes_priority_over_inherited_key(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"OPENAI_API_KEY": "fixture-inherited"}, clear=True):
            path = Path(folder) / ".env"
            path.write_text("LLM_PROVIDER=openai_compatible\nOPENAI_API_KEY=fixture-local\nOPENAI_BASE_URL=https://example.test/v1\n", encoding="utf-8")
            load_runtime_env(path)
            self.assertEqual(get_llm().openai_api_key.get_secret_value(), "fixture-local")

    def test_local_endpoint_is_paired_with_local_key_over_desktop_endpoint(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"OPENAI_API_KEY": "fixture-inherited", "LLM_BASE_URL": "https://inherited.example.test/v1", "OPENAI_BASE_URL": "https://other.example.test/v1"}, clear=True):
            path = Path(folder) / ".env"
            path.write_text("LLM_PROVIDER=openai_compatible\nOPENAI_API_KEY=fixture-local\nOPENAI_BASE_URL=https://project.example.test/v1\nLLM_BASE_URL=\n", encoding="utf-8")
            load_runtime_env(path)
            llm = get_llm()
            self.assertEqual(llm.openai_api_base, "https://project.example.test/v1")
            self.assertEqual(llm.openai_api_key.get_secret_value(), "fixture-local")

    def test_compatible_key_without_endpoint_cannot_fall_back_to_openrouter(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai_compatible", "OPENAI_API_KEY": "fixture-key"}, clear=True):
            with self.assertRaisesRegex(ValueError, "Base URL"):
                load_runtime_env("nonexistent-fixture.env")
            self.assertNotIn("OPENROUTER_API_KEY", os.environ)

    def test_openai_compatible_key_maps_in_process_without_rewriting_env(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            path = Path(folder) / ".env"
            content = "LLM_PROVIDER=openai_compatible\nOPENAI_API_KEY=fixture-key\nOPENAI_BASE_URL=https://example.test/v1\nLLM_MODEL=gpt-6-luna\n"
            path.write_text(content, encoding="utf-8")
            load_runtime_env(path)
            llm = get_llm()
            self.assertEqual(llm.model_name, "gpt-6-luna")
            self.assertEqual(llm.openai_api_base, "https://example.test/v1")
            self.assertEqual(llm.openai_api_key.get_secret_value(), "fixture-key")
            self.assertEqual(path.read_text(encoding="utf-8"), content)

    def test_openrouter_configuration_keeps_its_own_key(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "openrouter", "OPENROUTER_API_KEY": "fixture-openrouter", "OPENAI_API_KEY": "fixture-other"}, clear=True):
            load_runtime_env("nonexistent-fixture.env")
            self.assertEqual(os.environ["OPENROUTER_API_KEY"], "fixture-openrouter")

    def test_missing_openai_key_does_not_reuse_stale_other_provider_key(self):
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai_compatible", "OPENROUTER_API_KEY": "fixture-stale"}, clear=True):
            load_runtime_env("nonexistent-fixture.env")
            self.assertNotIn("OPENROUTER_API_KEY", os.environ)


if __name__ == "__main__":
    unittest.main()
