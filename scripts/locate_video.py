#!/usr/bin/env python3
"""
Finds the exact final generated video file from MoneyPrinterTurbo storage.
Prioritizes:
1. Videos listed in the newest storage/tasks/<task_id>/task.json
2. storage/tasks/**/final-*.mp4 (sorted by modification time, newest first)
"""
import glob
import json
import os
import sys


def locate_final_video() -> str | None:
    # 1. Try reading newest task.json
    task_json_files = glob.glob("storage/tasks/*/task.json")
    if task_json_files:
        # Sort by mtime descending (newest task first)
        task_json_files.sort(key=os.path.getmtime, reverse=True)
        for task_file in task_json_files:
            try:
                with open(task_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                videos = data.get("videos", [])
                for v in videos:
                    # Resolve relative or absolute path
                    if os.path.exists(v):
                        return os.path.abspath(v)
                    # If relative to storage or root
                    rel_v = os.path.join(os.path.dirname(task_file), os.path.basename(v))
                    if os.path.exists(rel_v):
                        return os.path.abspath(rel_v)
            except Exception as e:
                print(f"[!] Warning reading {task_file}: {e}", file=sys.stderr)

    # 2. Search for final-*.mp4 files under storage/tasks/
    final_videos = glob.glob("storage/tasks/**/final-*.mp4", recursive=True)
    if not final_videos:
        final_videos = glob.glob("storage/**/final-*.mp4", recursive=True)

    if final_videos:
        # Exclude temporary moviepy / intermediate files
        valid_videos = [
            v for v in final_videos
            if not os.path.basename(v).startswith(".")
            and "TEMP_MPY" not in v
            and os.path.getsize(v) > 0
        ]
        if valid_videos:
            valid_videos.sort(key=os.path.getmtime, reverse=True)
            return os.path.abspath(valid_videos[0])

    return None


def main():
    video_path = locate_final_video()
    if not video_path:
        print("[!] Error: No final generated video (final-*.mp4) found in storage.", file=sys.stderr)
        sys.exit(1)

    print(video_path)


if __name__ == "__main__":
    main()
