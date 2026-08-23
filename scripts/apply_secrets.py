#!/usr/bin/env python3
"""
Copies config.example.toml -> config.toml and patches only the fields
needed for the automated pipeline, using values from environment variables.
Everything else in the file is left untouched.

Expected env vars (set as GitHub Actions secrets):
  LLM_PROVIDER (optional: groq, gemini, openai, deepseek)
  GROQ_API_KEY
  GEMINI_API_KEY
  OPENAI_API_KEY
  DEEPSEEK_API_KEY
  PEXELS_API_KEY
  PIXABAY_API_KEY
  UPLOAD_POST_API_KEY
  UPLOAD_POST_USERNAME
"""
import os
import re
import shutil
import sys

SRC = "config.example.toml"
DST = "config.toml"


def env(name: str, warn: bool = False) -> str:
    value = os.environ.get(name, "").strip()
    if not value and warn:
        print(f"::warning::Environment variable {name} is empty", file=sys.stderr)
    return value


def get_llm_provider() -> str:
    explicit = env("LLM_PROVIDER").lower()
    if explicit:
        return explicit
    if env("GEMINI_API_KEY"):
        return "gemini"
    if env("OPENAI_API_KEY"):
        return "openai"
    if env("DEEPSEEK_API_KEY"):
        return "deepseek"
    if env("GROQ_API_KEY"):
        return "groq"
    return "groq"


REPLACEMENTS = {
    r'^llm_provider = .*$':
        lambda: f'llm_provider = "{get_llm_provider()}"',
    r'^pexels_api_keys = \[\]$':
        lambda: f'pexels_api_keys = ["{env("PEXELS_API_KEY", warn=True)}"]' if env("PEXELS_API_KEY") else 'pexels_api_keys = []',
    r'^pixabay_api_keys = \[\]$':
        lambda: f'pixabay_api_keys = ["{env("PIXABAY_API_KEY", warn=True)}"]' if env("PIXABAY_API_KEY") else 'pixabay_api_keys = []',
    r'^groq_api_key = ""$':
        lambda: f'groq_api_key = "{env("GROQ_API_KEY")}"',
    r'^gemini_api_key = ""$':
        lambda: f'gemini_api_key = "{env("GEMINI_API_KEY")}"',
    r'^gemini_model_name = ""$':
        lambda: f'gemini_model_name = "{env("GEMINI_MODEL_NAME") or "gemini-2.5-flash"}"' if env("GEMINI_API_KEY") else 'gemini_model_name = ""',
    r'^openai_api_key = ""$':
        lambda: f'openai_api_key = "{env("OPENAI_API_KEY")}"',
    r'^deepseek_api_key = ""$':
        lambda: f'deepseek_api_key = "{env("DEEPSEEK_API_KEY")}"',
    r'^subtitle_provider = .*$':
        'subtitle_provider = "edge"',
    r'^upload_post_enabled = false$':
        lambda: 'upload_post_enabled = true' if env("UPLOAD_POST_API_KEY") else 'upload_post_enabled = false',
    r'^upload_post_api_key = ""$':
        lambda: f'upload_post_api_key = "{env("UPLOAD_POST_API_KEY")}"',
    r'^upload_post_username = ""$':
        lambda: f'upload_post_username = "{env("UPLOAD_POST_USERNAME")}"',
    r'^upload_post_platforms = \["tiktok", "instagram"\]$':
        'upload_post_platforms = ["tiktok", "instagram"]',
    r'^upload_post_auto_upload = false$':
        lambda: 'upload_post_auto_upload = true' if env("UPLOAD_POST_API_KEY") else 'upload_post_auto_upload = false',
}


def main() -> None:
    if not os.path.exists(SRC):
        print(f"Missing {SRC}", file=sys.stderr)
        sys.exit(1)

    shutil.copyfile(SRC, DST)

    with open(DST, "r", encoding="utf-8") as f:
        lines = f.readlines()

    out = []
    for line in lines:
        stripped = line.rstrip("\n")
        replaced = stripped
        for pattern, repl in REPLACEMENTS.items():
            if re.match(pattern, stripped):
                replaced = repl() if callable(repl) else repl
                break
        out.append(replaced + "\n")

    with open(DST, "w", encoding="utf-8") as f:
        f.writelines(out)

    print(f"Wrote {DST} with secrets applied (LLM provider: {get_llm_provider()}).")


if __name__ == "__main__":
    main()
