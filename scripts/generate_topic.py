#!/usr/bin/env python3
"""
Smart Topic Selector and Generator for MoneyPrinterTurbo CI/CD.

Logic:
1. If the user provided a custom subject via CLI/Input, use it.
2. If data/topics_queue.txt has pending topics, take the top one.
3. Otherwise, use Gemini / LLM to generate a brand new, viral, unique topic
   that has NEVER been used before in data/used_topics.json.
4. Save the topic to data/used_topics.json to prevent future repetition.
"""
import argparse
import datetime
import json
import os
import sys

DATA_DIR = "data"
USED_TOPICS_FILE = os.path.join(DATA_DIR, "used_topics.json")
QUEUE_FILE = os.path.join(DATA_DIR, "topics_queue.txt")


def load_used_topics() -> list[str]:
    if not os.path.exists(USED_TOPICS_FILE):
        return []
    try:
        with open(USED_TOPICS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [item.get("topic", "").strip() for item in data if isinstance(item, dict) and item.get("topic")]
    except Exception as e:
        print(f"[!] Warning reading {USED_TOPICS_FILE}: {e}", file=sys.stderr)
        return []


def save_used_topic(topic: str):
    os.makedirs(DATA_DIR, exist_ok=True)
    records = []
    if os.path.exists(USED_TOPICS_FILE):
        try:
            with open(USED_TOPICS_FILE, "r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception:
            records = []

    # Check if already present
    existing = {r.get("topic", "").lower().strip() for r in records if isinstance(r, dict)}
    if topic.lower().strip() not in existing:
        records.append({
            "topic": topic.strip(),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })

    with open(USED_TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)


def pop_from_queue() -> str | None:
    if not os.path.exists(QUEUE_FILE):
        return None
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines()]

        valid_topics = [line for line in lines if line and not line.startswith("#")]
        if not valid_topics:
            return None

        chosen_topic = valid_topics[0]
        # Remove chosen topic from file
        remaining = []
        removed = False
        for line in lines:
            if not removed and line.strip() == chosen_topic:
                removed = True
                continue
            remaining.append(line)

        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(remaining) + "\n")

        return chosen_topic
    except Exception as e:
        print(f"[!] Warning reading queue: {e}", file=sys.stderr)
        return None


def generate_new_topic_with_llm(used_topics: list[str]) -> str:
    prompt = (
        "You are an expert viral content creator for YouTube Shorts and Instagram Reels.\n"
        "Generate ONE exciting, curiosity-inducing, educational topic for a 45-60 second short video.\n"
        "Categories: Technology, AI, Science, Productivity, Psychology, or Future Tech.\n"
        "CRITICAL RULE: The topic MUST be completely distinct and NOT repeat or closely rephrase any of these previously covered topics:\n"
        + "\n".join(f"- {t}" for t in used_topics[-30:]) + "\n\n"
        "Output ONLY the single topic title (max 10 words, under 60 characters). Do not include quotes, hashtags, or markdown."
    )

    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if gemini_key:
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            model_name = os.environ.get("GEMINI_MODEL_NAME", "gemini-3.6-flash")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            text = response.text.strip().strip('"\'').strip()
            if text:
                return text
        except Exception as e:
            print(f"[!] Gemini topic generation failed: {e}", file=sys.stderr)

    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.choices[0].message.content.strip().strip('"\'').strip()
            if text:
                return text
        except Exception as e:
            print(f"[!] Groq topic generation failed: {e}", file=sys.stderr)

    # Fallback default topics if LLM fails
    fallbacks = [
        "How Brain-Computer Interfaces Will Change Humanity",
        "3 Secret AI Features Built Into Your Phone",
        "The Mind-Bending Physics of Black Holes Explained",
        "Why Multi-Tasking Destroys Your Focus and Brain",
        "The Next Big Revolution After Generative AI",
    ]
    used_lower = {t.lower() for t in used_topics}
    for f in fallbacks:
        if f.lower() not in used_lower:
            return f

    return f"Future Tech Insights Part {len(used_topics) + 1}"


def main():
    parser = argparse.ArgumentParser(description="Select or generate a unique video topic")
    parser.add_argument("--input-subject", type=str, default="", help="User provided topic input")
    args = parser.parse_args()

    used_topics = load_used_topics()
    chosen_topic = ""

    # 1. Custom input from user
    if args.input_subject and args.input_subject.strip():
        chosen_topic = args.input_subject.strip()
        print(f"[*] Using custom user topic: {chosen_topic}")

    # 2. Topic queue file
    if not chosen_topic:
        queued = pop_from_queue()
        if queued:
            chosen_topic = queued
            print(f"[*] Picked topic from queue: {chosen_topic}")

    # 3. AI Generated unique topic
    if not chosen_topic:
        print("[*] Generating unique topic with AI (avoiding past topics)...")
        chosen_topic = generate_new_topic_with_llm(used_topics)
        print(f"[*] Generated fresh topic: {chosen_topic}")

    # Save to used topics
    save_used_topic(chosen_topic)

    # Write to GitHub Actions output if in CI
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output and os.path.exists(github_output):
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"subject={chosen_topic}\n")

    print(f"\nFINAL TOPIC: {chosen_topic}")


if __name__ == "__main__":
    main()
