"""
Pydantic schemas for the Semantic Visual Engine and Scene Planner.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class VisualIntent(BaseModel):
    """
    Detailed visual requirements for a single narration scene.
    """
    subject: str = Field(description="Primary visual subject of the scene")
    location: Optional[str] = Field(default="", description="Specific geographical location or landmark if applicable")
    objects: List[str] = Field(default_factory=list, description="Key visible items or props")
    action: str = Field(default="", description="Movement, action, or camera motion occurring in the scene")
    style: str = Field(default="realistic documentary footage", description="Cinematic style or visual atmosphere")
    stock_queries: List[str] = Field(default_factory=list, description="Search queries for stock providers, ordered from specific to broad")
    ai_prompt: str = Field(default="", description="High-detail positive prompt for AI video/image generator")
    negative_prompt: List[str] = Field(default_factory=list, description="Forbidden elements to prevent hallucinations or irrelevant content")
    visual_priority: str = Field(default="high", description="Scene visual priority: high | medium | low")
    factual_visual: bool = Field(default=False, description="True if the location/subject must be visually authentic")


class ScenePlan(BaseModel):
    """
    A single timed narration segment paired with its visual intent.
    """
    scene_id: str = Field(description="Unique scene identifier, e.g. scene_001")
    scene_index: int = Field(description="1-indexed sequence number")
    narration: str = Field(description="Narration sentence or segment spoken during this scene")
    start_time: float = Field(default=0.0, description="Start timestamp in seconds")
    end_time: float = Field(default=0.0, description="End timestamp in seconds")
    duration_seconds: float = Field(default=0.0, description="Target clip duration in seconds")
    visual_intent: VisualIntent


class ScenePlanningResult(BaseModel):
    """
    Result of the scene planning process for an entire video.
    """
    scenes: List[ScenePlan] = Field(default_factory=list, description="List of timed visual scene plans")
    total_duration: float = Field(default=0.0, description="Total video duration in seconds")
    status: str = Field(default="success", description="Status: 'success' | 'fallback' | 'failed'")
    fallback_used: bool = Field(default=False, description="True if rule-based fallback was used instead of LLM")
    raw_response: Optional[str] = Field(default=None, description="Raw LLM response text for debugging")


class RelevanceScore(BaseModel):
    """
    Evaluation score (0-100) assessing how closely a candidate video asset matches a visual intent.
    """
    total_score: float = Field(default=0.0, description="Overall relevance score from 0.0 to 100.0")
    location_score: float = Field(default=0.0, description="Points earned for geographic location match (max 30)")
    subject_score: float = Field(default=0.0, description="Points earned for primary subject match (max 30)")
    object_score: float = Field(default=0.0, description="Points earned for visible objects match (max 15)")
    action_score: float = Field(default=0.0, description="Points earned for action/motion match (max 10)")
    semantic_score: float = Field(default=0.0, description="Points earned for semantic narration match (max 10)")
    aspect_score: float = Field(default=0.0, description="Points earned for aspect ratio match (max 5)")
    negative_penalty: float = Field(default=0.0, description="Negative points applied if forbidden terms are detected (e.g. -50)")
    is_accepted: bool = Field(default=False, description="True if score meets or exceeds the required threshold")
    rejection_reason: Optional[str] = Field(default=None, description="Explanation if candidate was rejected")


class ScoredCandidate(BaseModel):
    """
    A downloaded and verified video asset matching a specific scene plan.
    """
    scene_id: str = Field(description="Associated scene identifier, e.g. scene_001")
    url: str = Field(description="Remote asset URL")
    local_path: str = Field(description="Local file path on disk")
    duration: float = Field(default=0.0, description="Duration of the asset in seconds")
    width: int = Field(default=0, description="Video width in pixels")
    height: int = Field(default=0, description="Video height in pixels")
    score: RelevanceScore = Field(description="Calculated relevance score")
    query_used: str = Field(default="", description="Search query string that discovered this asset")
    provider: str = Field(default="pexels", description="Stock provider name (e.g. pexels, pixabay)")
    source_info: Dict[str, Any] = Field(default_factory=dict, description="Metadata recorded from the stock provider")


class VideoAsset(BaseModel):
    """
    Normalized video asset produced by AI video generators or retrieved from semantic cache.
    """
    asset_id: str = Field(description="Unique identifier / content hash for this asset")
    file_path: str = Field(description="Local file path on disk")
    duration: float = Field(default=0.0, description="Duration in seconds")
    width: int = Field(default=0, description="Width in pixels")
    height: int = Field(default=0, description="Height in pixels")
    source_type: str = Field(default="ai_t2v", description="'ai_t2v' | 'ai_i2v' | 'stock' | 'mock'")
    provider: str = Field(default="huggingface", description="Provider name")
    model: str = Field(default="", description="Model name, e.g. Wan-AI/Wan2.2-TI2V-5B")
    seed: Optional[int] = Field(default=None, description="Random seed used for generation")
    prompt_used: str = Field(default="", description="Positive prompt sent to provider")
    negative_prompt_used: List[str] = Field(default_factory=list, description="Negative prompt list sent to provider")
    cached: bool = Field(default=False, description="True if retrieved from semantic cache")
