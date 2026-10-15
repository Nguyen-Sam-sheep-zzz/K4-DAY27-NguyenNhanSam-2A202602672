"""Load local provider settings without changing the supplied common factory."""
import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


def load_runtime_env(dotenv_path: str | Path = ".env") -> None:
    local = dotenv_values(dotenv_path, encoding="utf-8")
    load_dotenv(dotenv_path, encoding="utf-8")
    provider = local.get("LLM_PROVIDER", os.environ.get("LLM_PROVIDER", "openrouter"))
    if provider != "openai_compatible":
        return
    # The provided factory reads this legacy name. Map only in this process;
    # never copy credentials back into a file or reuse a different provider key.
    # An explicit project credential wins over an inherited desktop credential.
    key = local.get("OPENAI_API_KEY") if "OPENAI_API_KEY" in local else os.environ.get("OPENAI_API_KEY")
    os.environ.pop("OPENROUTER_API_KEY", None)
    if not key:
        return
    # Resolve local endpoint settings together. A local blank override means
    # use the local OPENAI_BASE_URL, never an unrelated desktop endpoint.
    source = local if any(name in local for name in ("LLM_BASE_URL", "OPENAI_BASE_URL")) else os.environ
    base = source.get("LLM_BASE_URL") or source.get("OPENAI_BASE_URL")
    if not base:
        raise ValueError("Set a Base URL: LLM_BASE_URL or OPENAI_BASE_URL for openai_compatible.")
    os.environ["LLM_BASE_URL"] = base
    os.environ["OPENROUTER_API_KEY"] = key
    if local.get("LLM_MODEL"):
        os.environ["LLM_MODEL"] = local["LLM_MODEL"]
