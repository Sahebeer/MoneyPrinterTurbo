"""
Search Scorer for evaluating semantic relevance of stock video candidates against VisualIntent.
"""
import re
from typing import Set
from app.models.schema import MaterialInfo, VideoAspect
from app.services.visual_engine.schema import RelevanceScore, VisualIntent

STOPWORDS: Set[str] = {
    "a", "an", "the", "in", "on", "at", "of", "to", "for", "with", "by", "from",
    "is", "are", "was", "were", "and", "or", "but", "as", "into", "through",
    "this", "that", "these", "those", "its", "their", "video", "footage", "clip",
    "4k", "hd", "cinematic", "realistic", "documentary"
}


def _tokenize(text: str) -> Set[str]:
    """Tokenize text into lowercase alphanumeric keywords without stopwords."""
    if not text:
        return set()
    words = re.findall(r'[a-zA-Z0-9_-]{2,}', text.lower())
    return {w for w in words if w not in STOPWORDS}


def _extract_candidate_text(candidate: MaterialInfo) -> str:
    """Extract and aggregate all searchable text metadata from a MaterialInfo object."""
    parts = []
    if candidate.url:
        # Extract meaningful words from URL path (e.g. /video/kerala-backwaters-houseboat-12345/)
        parts.append(candidate.url.replace("-", " ").replace("_", " ").replace("/", " "))

    source = candidate.source_info if isinstance(candidate.source_info, dict) else {}
    for key in ("search_term", "title", "description", "tags", "tags_list", "name"):
        val = source.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val)
        elif isinstance(val, list):
            parts.extend(str(item) for item in val if item)

    creator = source.get("creator")
    if isinstance(creator, dict):
        parts.append(str(creator.get("name") or ""))

    return " ".join(parts).lower()


def score_candidate(
    candidate: MaterialInfo,
    intent: VisualIntent,
    requested_aspect: VideoAspect | str = "9:16",
    factual_threshold: float = 80.0,
    generic_threshold: float = 65.0,
) -> RelevanceScore:
    """
    Evaluates how accurately a stock video candidate satisfies a scene's VisualIntent.

    Scoring Dimensions:
    - Location Match: max 30 pts (or 30 if non-geographic)
    - Subject Match: max 30 pts
    - Object Match: max 15 pts
    - Action Match: max 10 pts
    - Semantic / Context Match: max 10 pts
    - Aspect Ratio Match: max 5 pts
    - Negative Penalty: -50 pts if forbidden terms are detected

    Thresholds:
    - Factual Scene (`factual_visual=True`): requires >= factual_threshold (default 80.0)
    - Generic Scene (`factual_visual=False`): requires >= generic_threshold (default 65.0)
    """
    candidate_text = _extract_candidate_text(candidate)
    candidate_tokens = _tokenize(candidate_text)

    # 1. Negative Prompts Penalty Check (-50 pts)
    negative_penalty = 0.0
    rejection_reason = None

    for neg_term in intent.negative_prompt:
        neg_clean = neg_term.strip().lower()
        if not neg_clean:
            continue
        # Check direct substring or token match
        if neg_clean in candidate_text or any(token in candidate_tokens for token in _tokenize(neg_clean)):
            negative_penalty = -50.0
            rejection_reason = f"Rejected: Contains forbidden negative keyword '{neg_clean}'"
            break

    # 2. Location Match (max 30 pts)
    location_score = 0.0
    if intent.location and intent.location.strip():
        loc_tokens = _tokenize(intent.location)
        if loc_tokens:
            matched_loc = loc_tokens.intersection(candidate_tokens)
            if matched_loc:
                # If core city/landmark/state matches, grant full points
                ratio = len(matched_loc) / len(loc_tokens)
                location_score = 30.0 if ratio >= 0.5 else round(30.0 * (ratio / 0.5), 1)
            else:
                # Direct substring check for any location token
                for token in loc_tokens:
                    if token in candidate_text:
                        location_score = 30.0
                        break
    else:
        # Non-geographic scene receives full location points
        location_score = 30.0

    # 3. Subject Match (max 30 pts)
    subject_score = 0.0
    subject_tokens = _tokenize(intent.subject)
    if subject_tokens:
        matched_subj = subject_tokens.intersection(candidate_tokens)
        if matched_subj:
            ratio = len(matched_subj) / len(subject_tokens)
            subject_score = round(30.0 * min(ratio / 0.6, 1.0), 1)
        else:
            # Check queries overlap as fallback
            query_tokens = set().union(*[_tokenize(q) for q in intent.stock_queries])
            matched_queries = query_tokens.intersection(candidate_tokens)
            if matched_queries:
                subject_score = round(20.0 * (len(matched_queries) / len(query_tokens)), 1)
    else:
        subject_score = 30.0

    # 4. Object Match (max 15 pts)
    object_score = 0.0
    if intent.objects:
        obj_tokens = set().union(*[_tokenize(obj) for obj in intent.objects])
        if obj_tokens:
            matched_obj = obj_tokens.intersection(candidate_tokens)
            ratio = len(matched_obj) / len(obj_tokens)
            object_score = round(15.0 * min(ratio / 0.4, 1.0), 1)
    else:
        object_score = 15.0

    # 5. Action Match (max 10 pts)
    action_score = 0.0
    action_tokens = _tokenize(intent.action)
    if action_tokens:
        matched_act = action_tokens.intersection(candidate_tokens)
        if matched_act:
            ratio = len(matched_act) / len(action_tokens)
            action_score = round(10.0 * min(ratio / 0.3, 1.0), 1)
        else:
            action_score = 5.0
    else:
        action_score = 10.0

    # 6. Semantic / Query Match (max 10 pts)
    semantic_score = 0.0
    all_query_tokens = set().union(*[_tokenize(q) for q in intent.stock_queries])
    if all_query_tokens:
        matched_q = all_query_tokens.intersection(candidate_tokens)
        if matched_q:
            ratio = len(matched_q) / len(all_query_tokens)
            semantic_score = round(10.0 * min(ratio / 0.4, 1.0), 1)
        else:
            semantic_score = 5.0
    else:
        semantic_score = 10.0

    # 7. Aspect Ratio Match (max 5 pts)
    aspect_score = 5.0  # Stock APIs already filter by orientation; default to 5.0
    aspect_str = str(requested_aspect.value if hasattr(requested_aspect, "value") else requested_aspect).lower()
    source = candidate.source_info if isinstance(candidate.source_info, dict) else {}
    rendition = source.get("rendition") if isinstance(source.get("rendition"), dict) else {}
    width = getattr(candidate, "width", 0) or rendition.get("width") or source.get("width") or 0
    height = getattr(candidate, "height", 0) or rendition.get("height") or source.get("height") or 0
    try:
        width = int(width)
        height = int(height)
    except (ValueError, TypeError):
        width, height = 0, 0

    if width > 0 and height > 0:
        if aspect_str in ("9:16", "portrait"):
            aspect_score = 5.0 if height > width else 0.0
        elif aspect_str in ("16:9", "landscape"):
            aspect_score = 5.0 if width > height else 0.0
        elif aspect_str in ("1:1", "square"):
            aspect_score = 5.0 if abs(width - height) / max(width, height) < 0.1 else 0.0

    # Calculate Total Score
    raw_total = (
        location_score
        + subject_score
        + object_score
        + action_score
        + semantic_score
        + aspect_score
        + negative_penalty
    )
    total_score = round(max(0.0, min(100.0, raw_total)), 1)

    required_threshold = factual_threshold if intent.factual_visual else generic_threshold
    is_accepted = (total_score >= required_threshold) and (negative_penalty == 0.0)

    if not is_accepted and not rejection_reason:
        rejection_reason = (
            f"Score {total_score} below required threshold {required_threshold} "
            f"({'factual' if intent.factual_visual else 'generic'} scene)"
        )

    return RelevanceScore(
        total_score=total_score,
        location_score=location_score,
        subject_score=subject_score,
        object_score=object_score,
        action_score=action_score,
        semantic_score=semantic_score,
        aspect_score=aspect_score,
        negative_penalty=negative_penalty,
        is_accepted=is_accepted,
        rejection_reason=rejection_reason if not is_accepted else None,
    )
