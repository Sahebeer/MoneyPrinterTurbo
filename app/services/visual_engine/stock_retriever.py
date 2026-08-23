"""
Semantic Stock Retriever for discovering and scoring stock footage tailored to visual scenes.
Reuses existing Pexels and Pixabay search and caching logic from app.services.material.
"""
import os
from typing import List, Optional
from loguru import logger

from app.config import config
from app.models.schema import MaterialInfo, VideoAspect
from app.services import material
from app.services.visual_engine.schema import ScenePlan, ScoredCandidate
from app.services.visual_engine.search_scorer import score_candidate


def retrieve_stock_for_scene(
    scene: ScenePlan,
    source: str = "pexels",
    video_aspect: VideoAspect | str = "9:16",
    material_directory: str = "",
    app_config: Optional[dict] = None,
) -> Optional[ScoredCandidate]:
    """
    Searches Pexels/Pixabay hierarchically using the scene's visual intent queries,
    scores candidate clips for semantic relevance, and downloads the best matching clip.

    Returns:
        ScoredCandidate if a candidate meets the relevance threshold, else None.
    """
    cfg = app_config or config.app
    visual_cfg = cfg.get("visual_engine", {})
    factual_threshold = float(visual_cfg.get("factual_min_score", 80.0))
    generic_threshold = float(visual_cfg.get("stock_min_score", 65.0))

    queries = scene.visual_intent.stock_queries
    if not queries:
        queries = [scene.visual_intent.subject or "cinematic footage"]

    # Minimum acceptable clip duration based on target scene duration
    min_duration = min(int(scene.duration_seconds), 3) if scene.duration_seconds > 0 else 3

    logger.info(
        f"semantic stock search for {scene.scene_id}: "
        f"queries={queries}, factual={scene.visual_intent.factual_visual}, "
        f"target_dur={scene.duration_seconds:.1f}s"
    )

    best_accepted_candidate: Optional[MaterialInfo] = None
    best_score = None
    best_query = ""

    for query in queries:
        query_str = query.strip()
        if not query_str:
            continue

        candidates: List[MaterialInfo] = []
        try:
            if source == "pixabay":
                candidates = material._search_videos_with_cache(
                    material.search_videos_pixabay,
                    search_term=query_str,
                    minimum_duration=min_duration,
                    video_aspect=video_aspect,
                )
            else:  # default pexels
                candidates = material._search_videos_with_cache(
                    material.search_videos_pexels,
                    search_term=query_str,
                    minimum_duration=min_duration,
                    video_aspect=video_aspect,
                )
        except Exception as exc:
            logger.warning(f"stock search failed for query '{query_str}' on {source}: {exc}")
            continue

        if not candidates:
            continue

        # Score all returned candidates
        for candidate in candidates:
            score = score_candidate(
                candidate=candidate,
                intent=scene.visual_intent,
                requested_aspect=video_aspect,
                factual_threshold=factual_threshold,
                generic_threshold=generic_threshold,
            )

            if score.is_accepted:
                if best_score is None or score.total_score > best_score.total_score:
                    best_score = score
                    best_accepted_candidate = candidate
                    best_query = query_str

        # If a strong match was found for a specific query, proceed immediately
        if best_accepted_candidate and best_score and best_score.total_score >= 85.0:
            break

    if not best_accepted_candidate or not best_score:
        logger.info(f"[VISUAL] Scene {scene.scene_index} → {source.capitalize()} → rejected")
        return None

    # Save video locally using existing material conventions
    try:
        local_path = material.save_video(
            video_url=best_accepted_candidate.url,
            save_dir=material_directory,
        )
        if not local_path or not os.path.exists(local_path):
            logger.warning(f"failed to download stock video from {best_accepted_candidate.url}")
            return None

        logger.success(
            f"accepted stock asset for {scene.scene_id}: score={best_score.total_score} "
            f"(query='{best_query}'), saved to {local_path}"
        )

        source_dict = (
            best_accepted_candidate.source_info
            if isinstance(best_accepted_candidate.source_info, dict)
            else {}
        )
        rendition_dict = source_dict.get("rendition") if isinstance(source_dict.get("rendition"), dict) else {}
        w = getattr(best_accepted_candidate, "width", 0) or rendition_dict.get("width") or source_dict.get("width") or 0
        h = getattr(best_accepted_candidate, "height", 0) or rendition_dict.get("height") or source_dict.get("height") or 0

        return ScoredCandidate(
            scene_id=scene.scene_id,
            url=best_accepted_candidate.url,
            local_path=local_path,
            duration=best_accepted_candidate.duration,
            width=int(w),
            height=int(h),
            score=best_score,
            query_used=best_query,
            provider=source,
            source_info=source_dict,
        )

    except Exception as exc:
        logger.error(f"error saving stock video for {scene.scene_id}: {exc}")
        return None
