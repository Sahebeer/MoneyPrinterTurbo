"""
Semantic Visual Engine package for MoneyPrinterTurbo.
"""
from app.services.visual_engine.ai_provider import (
    BaseVideoProvider,
    HuggingFaceProvider,
    MockVideoProvider,
    get_video_provider,
)
from app.services.visual_engine.cache import (
    compute_asset_hash,
    get_cached_asset,
    store_cached_asset,
)
from app.services.visual_engine.engine import acquire_scene_materials
from app.services.visual_engine.schema import (
    RelevanceScore,
    ScenePlan,
    ScenePlanningResult,
    ScoredCandidate,
    VideoAsset,
    VisualIntent,
)
from app.services.visual_engine.scene_planner import plan_scenes
from app.services.visual_engine.search_scorer import score_candidate
from app.services.visual_engine.stock_retriever import retrieve_stock_for_scene

__all__ = [
    "VisualIntent",
    "ScenePlan",
    "ScenePlanningResult",
    "RelevanceScore",
    "ScoredCandidate",
    "VideoAsset",
    "BaseVideoProvider",
    "HuggingFaceProvider",
    "MockVideoProvider",
    "get_video_provider",
    "compute_asset_hash",
    "get_cached_asset",
    "store_cached_asset",
    "plan_scenes",
    "score_candidate",
    "retrieve_stock_for_scene",
    "acquire_scene_materials",
]
