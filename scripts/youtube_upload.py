#!/usr/bin/env python3
"""
Uploads a generated video file directly to YouTube using OAuth2 credentials.
Designed to run unattended in CI/CD (GitHub Actions) or locally.

Requires environment variables or CLI arguments:
  - YT_CLIENT_ID
  - YT_CLIENT_SECRET
  - YT_REFRESH_TOKEN

Usage:
  python scripts/youtube_upload.py --file "storage/tasks/xyz/final-1.mp4" --title "My Short" --privacy unlisted
"""
import argparse
import http.client
import os
import random
import sys
import time

import google.auth.exceptions
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# Explicitly retry on certain HTTP errors
RETRIABLE_EXCEPTIONS = (
    http.client.HTTPException,
    google.auth.exceptions.TransportError,
    IOError,
)
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
MAX_RETRIES = 5


def get_authenticated_service(client_id: str, client_secret: str, refresh_token: str):
    """Builds and returns the YouTube API client service."""
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"],
    )
    return build("youtube", "v3", credentials=creds)


def upload_video(
    youtube,
    file_path: str,
    title: str,
    description: str,
    tags: list[str],
    category_id: str = "22",
    privacy_status: str = "unlisted",
):
    """Uploads the video file to YouTube with resumable chunks."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Video file not found at: {file_path}")

    # YouTube title max length is 100 chars
    sanitized_title = title.strip()[:100] if title else "Generated Video"

    body = {
        "snippet": {
            "title": sanitized_title,
            "description": description or "",
            "tags": tags or [],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    # Use chunksize of 4MB for resumable upload
    chunk_size = 4 * 1024 * 1024
    media = MediaFileUpload(
        file_path,
        chunksize=chunk_size,
        resumable=True,
        mimetype="video/mp4",
    )

    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    print(f"[*] Starting upload for: {file_path}")
    print(f"[*] Title: {sanitized_title}")
    print(f"[*] Privacy: {privacy_status}")

    response = None
    retry = 0

    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                print(f"    Upload progress: {progress}%")
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                retry += 1
                if retry > MAX_RETRIES:
                    raise
                sleep_seconds = (2 ** retry) + random.random()
                print(f"[!] Retriable HTTP error {e.resp.status}. Retrying in {sleep_seconds:.1f}s...")
                time.sleep(sleep_seconds)
            else:
                raise
        except RETRIABLE_EXCEPTIONS as e:
            retry += 1
            if retry > MAX_RETRIES:
                raise
            sleep_seconds = (2 ** retry) + random.random()
            print(f"[!] Retriable connection error {e}. Retrying in {sleep_seconds:.1f}s...")
            time.sleep(sleep_seconds)

    video_id = response.get("id")
    video_url = f"https://youtu.be/{video_id}"
    print("\n" + "=" * 60)
    print(" SUCCESS: Video uploaded to YouTube!")
    print(f" Video ID:  {video_id}")
    print(f" Video URL: {video_url}")
    print("=" * 60)
    return video_id, video_url


def main():
    parser = argparse.ArgumentParser(description="Upload video to YouTube via OAuth2")
    parser.add_argument("--file", type=str, default="auto", help="Path to video file (or 'auto' to auto-detect)")
    parser.add_argument("--title", type=str, default="", help="Video title")
    parser.add_argument("--description", type=str, default="", help="Video description")
    parser.add_argument("--tags", type=str, default="", help="Comma-separated tags")
    parser.add_argument(
        "--privacy",
        type=str,
        choices=["public", "unlisted", "private"],
        default="unlisted",
        help="Video privacy status (default: unlisted)",
    )
    parser.add_argument("--category-id", type=str, default="22", help="YouTube category ID (default: 22 - People & Blogs)")
    parser.add_argument("--client-id", type=str, default=os.environ.get("YT_CLIENT_ID", ""))
    parser.add_argument("--client-secret", type=str, default=os.environ.get("YT_CLIENT_SECRET", ""))
    parser.add_argument("--refresh-token", type=str, default=os.environ.get("YT_REFRESH_TOKEN", ""))

    args = parser.parse_args()

    if not args.client_id or not args.client_secret or not args.refresh_token:
        print("[!] Error: Missing YouTube OAuth credentials.", file=sys.stderr)
        print("Provide them via CLI or set YT_CLIENT_ID, YT_CLIENT_SECRET, and YT_REFRESH_TOKEN environment variables.", file=sys.stderr)
        sys.exit(1)

    # Auto-resolve video path if requested or if file is missing/dir
    file_path = args.file
    if not file_path or file_path.lower() == "auto" or os.path.isdir(file_path) or not os.path.exists(file_path):
        try:
            from scripts.locate_video import locate_final_video
            detected = locate_final_video()
            if detected:
                file_path = detected
                print(f"[*] Auto-detected final video: {file_path}")
        except Exception as e:
            print(f"[!] Warning during video auto-detection: {e}", file=sys.stderr)

    import json
    import re

    description = args.description.strip()
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []

    # If description or tags are empty, discover from task.json or synthesize from topic
    if not description or not tags:
        task_dir = os.path.dirname(os.path.abspath(file_path))
        task_json_path = os.path.join(task_dir, "task.json")
        script_text = ""
        subject_text = args.title or ""
        if os.path.isfile(task_json_path):
            try:
                with open(task_json_path, "r", encoding="utf-8") as tf:
                    tdata = json.load(tf)
                script_text = tdata.get("script", "") or tdata.get("params", {}).get("video_script", "")
                if not subject_text:
                    subject_text = tdata.get("params", {}).get("video_subject", "")
                task_terms = tdata.get("terms", []) or []
                for term in task_terms:
                    clean_term = re.sub(r"[^\w]", "", term).lower()
                    if clean_term and clean_term not in tags:
                        tags.append(clean_term)
            except Exception:
                pass

        # Inject topic keywords as hashtags
        if subject_text:
            for word in re.findall(r"\b[A-Za-z]{3,}\b", subject_text):
                w_clean = word.lower()
                if w_clean not in tags and len(tags) < 15:
                    tags.append(w_clean)

        # Ensure top trending short tags
        core_tags = ["shorts", "viral", "trending", "fyp"]
        for ct in core_tags:
            if ct not in tags:
                tags.append(ct)

        if not description:
            topic_tags = " ".join(f"#{t}" for t in tags[:12])
            desc_body = script_text or subject_text or "Check out this amazing short video!"
            description = f"{desc_body}\n\n{topic_tags}"

    try:
        service = get_authenticated_service(args.client_id, args.client_secret, args.refresh_token)
        upload_video(
            youtube=service,
            file_path=file_path,
            title=args.title,
            description=description,
            tags=tags,
            category_id=args.category_id,
            privacy_status=args.privacy,
        )
    except Exception as e:
        print(f"[!] YouTube Upload failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
