"""
Semantic Visual Cache for AI-generated and processed video assets.
Provides deterministic SHA256 hashing and disk persistence for resumability.
"""
import hashlib
import json
import os
from typing import Any, Dict, List, Optional
from loguru import logger

from app.services.visual_engine.schema import VideoAsset
from app.utils import utils


def compute_asset_hash(
    prompt: str,
    negative_prompt: Optional[List[str]] = None,
    duration: float = 5.0,
    aspect: str = "9:16",
    seed: Optional[int] = None,
    model: str = "Wan-AI/Wan2.2-TI2V-5B",
    source_type: str = "ai_t2v",
    image_hash: str = "",
) -> str:
    """
    Computes a deterministic SHA256 hash identifying a generation request.
    """
    neg_str = ",".join(sorted(n.strip().lower() for n in (negative_prompt or [])))
    aspect_str = str(aspect.value if hasattr(aspect, "value") else aspect).lower().strip()
    raw_key = (
        f"model={model}|type={source_type}|prompt={prompt.strip().lower()}|"
        f"neg={neg_str}|dur={duration:.1f}|aspect={aspect_str}|seed={seed}|img={image_hash}"
    )
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:32]


def get_cached_asset(
    asset_hash: str,
    cache_dir: str = "",
) -> Optional[VideoAsset]:
    """
    Retrieves a cached VideoAsset if it exists on disk.
    """
    base_dir = cache_dir.strip() if cache_dir else os.path.join(utils.storage_dir(), "semantic_cache")
    asset_dir = os.path.join(base_dir, asset_hash)
    video_file = os.path.join(asset_dir, "clip.mp4")
    meta_file = os.path.join(asset_dir, "metadata.json")

    if os.path.isfile(video_file) and os.path.isfile(meta_file) and os.path.getsize(video_file) > 0:
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)

            logger.info(f"semantic cache hit for asset {asset_hash} at {video_file}")
            return VideoAsset(
                asset_id=asset_hash,
                file_path=video_file,
                duration=float(meta.get("duration", 0.0)),
                width=int(meta.get("width", 0)),
                height=int(meta.get("height", 0)),
                source_type=str(meta.get("source_type", "ai_t2v")),
                provider=str(meta.get("provider", "huggingface")),
                model=str(meta.get("model", "")),
                seed=meta.get("seed"),
                prompt_used=str(meta.get("prompt_used", "")),
                negative_prompt_used=meta.get("negative_prompt_used", []),
                cached=True,
            )
        except Exception as exc:
            logger.warning(f"failed to read cache metadata for {asset_hash}: {exc}")
            return None

    return None


def store_cached_asset(
    asset_hash: str,
    video_bytes: bytes,
    metadata: Dict[str, Any],
    cache_dir: str = "",
) -> str:
    """
    Persists a generated video and its metadata to the semantic visual cache.
    Returns the path to the saved video file.
    """
    base_dir = cache_dir.strip() if cache_dir else os.path.join(utils.storage_dir(), "semantic_cache")
    asset_dir = os.path.join(base_dir, asset_hash)
    os.makedirs(asset_dir, exist_ok=True)

    video_file = os.path.join(asset_dir, "clip.mp4")
    meta_file = os.path.join(asset_dir, "metadata.json")

    with open(video_file, "wb") as f:
        f.write(video_bytes)

    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    logger.info(f"persisted asset {asset_hash} ({len(video_bytes)} bytes) to cache: {video_file}")
    return video_file
