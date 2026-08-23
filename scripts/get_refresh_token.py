#!/usr/bin/env python3
"""
One-time script to generate a Google YouTube OAuth2 Refresh Token.
Run locally on your machine once to obtain:
  - YT_CLIENT_ID
  - YT_CLIENT_SECRET
  - YT_REFRESH_TOKEN

Usage:
  python scripts/get_refresh_token.py
  python scripts/get_refresh_token.py --client-secrets-file path/to/client_secret_xxx.json
  python scripts/get_refresh_token.py --client-id YOUR_CLIENT_ID --client-secret YOUR_CLIENT_SECRET
"""
import argparse
import glob
import json
import os
import sys
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


def find_default_client_secrets() -> str | None:
    patterns = [
        "client_secret*.json",
        os.path.expanduser("~/Downloads/client_secret*.json"),
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Obtain YouTube OAuth2 Refresh Token for GitHub Actions CI/CD"
    )
    parser.add_argument(
        "--client-secrets-file",
        type=str,
        default=None,
        help="Path to client_secret_*.json downloaded from Google Cloud Console",
    )
    parser.add_argument(
        "--client-id",
        type=str,
        default=None,
        help="Google OAuth Client ID",
    )
    parser.add_argument(
        "--client-secret",
        type=str,
        default=None,
        help="Google OAuth Client Secret",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Local port for OAuth redirect server (default: 8080)",
    )

    args = parser.parse_args()

    client_id = args.client_id
    client_secret = args.client_secret
    secrets_file = args.client_secrets_file

    if not client_id or not client_secret:
        if not secrets_file:
            secrets_file = find_default_client_secrets()

        if secrets_file and os.path.exists(secrets_file):
            print(f"[*] Found credentials file: {secrets_file}")
            with open(secrets_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Support both "installed" and "web" credential formats
            cfg = data.get("installed") or data.get("web")
            if cfg:
                client_id = cfg.get("client_id")
                client_secret = cfg.get("client_secret")
            else:
                print(f"[!] Invalid client_secrets.json structure: {secrets_file}", file=sys.stderr)
                sys.exit(1)
        else:
            print("[!] Error: No client secrets found.", file=sys.stderr)
            print("Please provide --client-secrets-file OR --client-id and --client-secret.", file=sys.stderr)
            sys.exit(1)

    print("\n" + "=" * 60)
    print(" YouTube OAuth2 Refresh Token Generator")
    print("=" * 60)
    print(f"Client ID: {client_id[:20]}... (truncated)")

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost", f"http://localhost:{args.port}"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)

    print("\nOpening your browser for Google authentication...")
    print("1. Log in with the Google Account that owns your YouTube channel.")
    print("2. If you see 'Google hasn't verified this app', click Advanced -> Go to ... (unsafe).")
    print("3. Allow the requested permissions.")
    print("-" * 60)

    try:
        credentials = flow.run_local_server(
            port=args.port,
            prompt="consent",
            access_type="offline",
        )
    except Exception as e:
        print(f"\n[!] Failed to run local server on port {args.port}: {e}")
        print("[*] Trying with dynamic port...")
        credentials = flow.run_local_server(
            port=0,
            prompt="consent",
            access_type="offline",
        )

    if not credentials.refresh_token:
        print("\n[!] WARNING: No refresh token returned!")
        print("This usually happens if consent was already granted.")
        print("Please visit: https://myaccount.google.com/permissions")
        print("Revoke access for your app, and re-run this script.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print(" SUCCESS! Copy these 3 values into your GitHub Secrets:")
    print("=" * 60)
    print(f"YT_CLIENT_ID:\n{client_id}\n")
    print(f"YT_CLIENT_SECRET:\n{client_secret}\n")
    print(f"YT_REFRESH_TOKEN:\n{credentials.refresh_token}\n")
    print("=" * 60)


if __name__ == "__main__":
    main()
