"""
Scene Planner for the Semantic Visual Engine.
Transforms video narration text into structured, timed visual scenes.
"""
import json
import re
from typing import List, Optional
from loguru import logger

from app.services import llm
from app.services.visual_engine.schema import ScenePlan, ScenePlanningResult, VisualIntent

SCENE_PLANNER_SYSTEM_PROMPT = """You are an expert cinematic visual director and scene planner for high-quality short-form videos.
Analyze the following narration script and break it down into sequential visual scenes (typically 3 to 8 scenes, each covering 4 to 10 seconds of spoken narration).

For each scene, output a JSON object with:
- "narration": The exact spoken text for this scene.
- "visual_intent":
  - "subject": Primary visual subject (e.g., "Kerala backwaters houseboat").
  - "location": Specific location/city/country if applicable, or "".
  - "objects": Array of specific visible elements (e.g., ["traditional houseboat", "palm trees", "waterways"]).
  - "action": Motion or activity occurring (e.g., "houseboat gliding slowly through tropical backwaters").
  - "style": Cinematic style (e.g., "realistic documentary footage, 4k, natural lighting").
  - "stock_queries": 2 to 4 search queries ordered from most specific to broad.
  - "ai_prompt": Detailed prompt describing the scene for image/video generation.
  - "negative_prompt": Array of forbidden objects, incorrect geography, or hallucinations to avoid.
  - "visual_priority": "high", "medium", or "low".
  - "factual_visual": true if this is an authentic real-world location/landmark/product, false if conceptual/generic.

CRITICAL RULES:
1. Cover the entire narration text in sequential order.
2. Return ONLY a valid JSON array of scene objects. Do not include markdown codeblocks or extra text.
"""


def _split_into_sentences(text: str) -> List[str]:
    """Split text into sentences across multiple languages (English, Chinese, Japanese, etc.)."""
    cleaned = text.strip()
    if not cleaned:
        return []
    # Split by standard sentence terminators (. ! ? \n 。 ！ ？) with optional whitespace
    parts = re.split(r'(?<=[.!?\n。！？])\s*', cleaned)
    sentences = [p.strip() for p in parts if p.strip()]
    if not sentences:
        # Fallback to paragraph split
        sentences = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
    return sentences or [cleaned]


def _distribute_timestamps(scenes: List[ScenePlan], total_duration: float) -> List[ScenePlan]:
    """
    Assigns precise start_time, end_time, and duration_seconds to each scene
    proportional to narration length, summing exactly to total_duration.
    """
    if not scenes:
        return scenes

    if total_duration <= 0.0:
        # Assign estimated default durations (e.g. 5s per scene)
        current_time = 0.0
        for idx, scene in enumerate(scenes):
            scene.scene_index = idx + 1
            scene.scene_id = f"scene_{idx + 1:03d}"
            scene.duration_seconds = 5.0
            scene.start_time = round(current_time, 2)
            scene.end_time = round(current_time + 5.0, 2)
            current_time += 5.0
        return scenes

    # Calculate weights based on character length of narration
    weights = [max(len(scene.narration.strip()), 1) for scene in scenes]
    total_weight = sum(weights)

    current_time = 0.0
    for idx, (scene, weight) in enumerate(zip(scenes, weights)):
        scene.scene_index = idx + 1
        scene.scene_id = f"scene_{idx + 1:03d}"
        scene.start_time = round(current_time, 2)

        if idx == len(scenes) - 1:
            # Last scene takes the exact remaining time to avoid rounding errors
            scene.end_time = round(total_duration, 2)
            scene.duration_seconds = round(max(total_duration - current_time, 0.1), 2)
        else:
            duration = round((weight / total_weight) * total_duration, 2)
            scene.duration_seconds = max(duration, 0.5)
            scene.end_time = round(current_time + scene.duration_seconds, 2)
            current_time = scene.end_time

    return scenes


def _fallback_rule_based_planning(
    video_script: str, total_duration: float = 0.0
) -> ScenePlanningResult:
    """
    Deterministic rule-based fallback if LLM scene planning fails.
    Splits narration into sentences and constructs basic VisualIntent objects.
    """
    logger.info("using rule-based fallback scene planner")
    sentences = _split_into_sentences(video_script)
    if not sentences:
        sentences = [video_script.strip() or "Scene"]

    scenes: List[ScenePlan] = []
    for idx, sentence in enumerate(sentences):
        # Extract basic keywords from sentence
        words = [w for w in re.findall(r'\b[A-Za-z0-9_-]{3,}\b', sentence)]
        subject = " ".join(words[:4]) if words else "Background Video"
        stock_queries = [subject, "cinematic footage", "background video"]

        intent = VisualIntent(
            subject=subject,
            location="",
            objects=words[:3],
            action="subtle motion",
            style="realistic documentary footage",
            stock_queries=stock_queries,
            ai_prompt=f"Cinematic realistic footage of {subject}, 4k, documentary style",
            negative_prompt=["blurry", "low quality", "distortion", "text", "watermark"],
            visual_priority="medium",
            factual_visual=False,
        )
        scenes.append(
            ScenePlan(
                scene_id=f"scene_{idx + 1:03d}",
                scene_index=idx + 1,
                narration=sentence,
                visual_intent=intent,
            )
        )

    timed_scenes = _distribute_timestamps(scenes, total_duration)
    return ScenePlanningResult(
        scenes=timed_scenes,
        total_duration=total_duration,
        status="fallback",
        fallback_used=True,
    )


def _parse_llm_json_response(raw_text: str) -> Optional[List[dict]]:
    """Strips markdown fences and parses raw JSON array."""
    cleaned = raw_text.strip()
    # Strip ```json ... ``` or ``` ... ```
    cleaned = llm._strip_code_fence(cleaned)

    # Search for outer JSON array if extra conversational text exists
    array_match = re.search(r'\[\s*\{.*\}\s*\]', cleaned, re.DOTALL)
    if array_match:
        cleaned = array_match.group(0)

    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "scenes" in data and isinstance(data["scenes"], list):
            return data["scenes"]
    except json.JSONDecodeError as exc:
        logger.warning(f"failed to parse LLM scene plan JSON: {exc}")
    return None


def plan_scenes(
    video_script: str,
    total_duration: float = 0.0,
    language: str = "",
    app_config: Optional[dict] = None,
) -> ScenePlanningResult:
    """
    Analyzes narration text and creates a structured, timed ScenePlanningResult.

    Args:
        video_script: The full voiceover / narration script text.
        total_duration: Exact audio duration in seconds (from TTS).
        language: Language code (e.g. 'en-US', 'zh-CN').
        app_config: Optional runtime app configuration dictionary.

    Returns:
        ScenePlanningResult containing validated ScenePlan items.
    """
    if not video_script or not video_script.strip():
        logger.warning("empty video_script passed to plan_scenes")
        return ScenePlanningResult(
            scenes=[], total_duration=0.0, status="failed", fallback_used=False
        )

    prompt = f"{SCENE_PLANNER_SYSTEM_PROMPT}\n\n# Narration Script:\n{video_script.strip()}"
    if language:
        prompt += f"\n- Language: {language}"

    logger.info(f"generating scene plan: narration_length={len(video_script)}, duration={total_duration:.1f}s")

    try:
        if app_config is None:
            raw_response = llm._generate_response(prompt=prompt)
        else:
            raw_response = llm._generate_response(prompt=prompt, app_config=app_config)

        if not raw_response or raw_response.startswith("Error:"):
            logger.warning(f"LLM scene planning returned error: {raw_response}")
            fallback = _fallback_rule_based_planning(video_script, total_duration)
            fallback.raw_response = raw_response
            return fallback

        scene_dicts = _parse_llm_json_response(raw_response)
        if not scene_dicts:
            logger.warning("LLM response did not contain valid scene array, falling back")
            fallback = _fallback_rule_based_planning(video_script, total_duration)
            fallback.raw_response = raw_response
            return fallback

        # Validate each scene item through Pydantic models
        validated_scenes: List[ScenePlan] = []
        for idx, item in enumerate(scene_dicts):
            if not isinstance(item, dict):
                continue

            narration = item.get("narration") or f"Scene {idx + 1}"
            raw_intent = item.get("visual_intent") or {}
            if not isinstance(raw_intent, dict):
                raw_intent = {}

            # Construct and validate VisualIntent
            intent = VisualIntent(
                subject=str(raw_intent.get("subject") or narration[:30]),
                location=str(raw_intent.get("location") or ""),
                objects=[str(o) for o in raw_intent.get("objects", []) if o],
                action=str(raw_intent.get("action") or ""),
                style=str(raw_intent.get("style") or "realistic documentary footage"),
                stock_queries=[str(q) for q in raw_intent.get("stock_queries", []) if q] or [str(raw_intent.get("subject") or "cinematic footage")],
                ai_prompt=str(raw_intent.get("ai_prompt") or f"Cinematic footage of {narration}"),
                negative_prompt=[str(n) for n in raw_intent.get("negative_prompt", []) if n] or ["blurry", "low quality", "distortion"],
                visual_priority=str(raw_intent.get("visual_priority") or "high"),
                factual_visual=bool(raw_intent.get("factual_visual", False)),
            )

            scene = ScenePlan(
                scene_id=f"scene_{idx + 1:03d}",
                scene_index=idx + 1,
                narration=narration,
                visual_intent=intent,
            )
            validated_scenes.append(scene)

        if not validated_scenes:
            logger.warning("no valid scenes parsed from LLM, falling back")
            fallback = _fallback_rule_based_planning(video_script, total_duration)
            fallback.raw_response = raw_response
            return fallback

        timed_scenes = _distribute_timestamps(validated_scenes, total_duration)
        logger.success(f"successfully generated {len(timed_scenes)} visual scenes")
        return ScenePlanningResult(
            scenes=timed_scenes,
            total_duration=total_duration,
            status="success",
            fallback_used=False,
            raw_response=raw_response,
        )

    except Exception as exc:
        logger.error(f"unexpected exception in plan_scenes: {exc}")
        return _fallback_rule_based_planning(video_script, total_duration)
