#!/usr/bin/env python3
"""
Copies config.example.toml -> config.toml and patches only the fields
needed for the automated pipeline, using values from environment variables.
Everything else in the file is left untouched.

Expected env vars (set as GitHub Actions secrets):
  GROQ_API_KEY
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

REPLACEMENTS = {
    r'^llm_provider = .*$':
        'llm_provider = "groq"',
    r'^pexels_api_keys = \[\]$':
        lambda: f'pexels_api_keys = ["{env("PEXELS_API_KEY")}"]',
    r'^pixabay_api_keys = \[\]$':
        lambda: f'pixabay_api_keys = ["{env("PIXABAY_API_KEY")}"]',
    r'^groq_api_key = ""$':
        lambda: f'groq_api_key = "{env("GROQ_API_KEY")}"',
    r'^subtitle_provider = .*$':
        'subtitle_provider = "edge"',
    r'^upload_post_enabled = false$':
        'upload_post_enabled = true',
    r'^upload_post_api_key = ""$':
        lambda: f'upload_post_api_key = "{env("UPLOAD_POST_API_KEY")}"',
    r'^upload_post_username = ""$':
        lambda: f'upload_post_username = "{env("UPLOAD_POST_USERNAME")}"',
    r'^upload_post_platforms = \["tiktok", "instagram"\]$':
        'upload_post_platforms = ["tiktok", "instagram"]',
    r'^upload_post_auto_upload = false$':
        'upload_post_auto_upload = true',
}


def env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        print(f"::warning::Environment variable {name} is empty", file=sys.stderr)
    return value


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

    print(f"Wrote {DST} with secrets applied.")


if __name__ == "__main__":
    main()
