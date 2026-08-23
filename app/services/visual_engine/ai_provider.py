"""
AI Video Provider abstraction and implementations (Hugging Face Wan2.2 TI2V-5B and MockProvider).
"""
import base64
import os
import random
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import requests
from loguru import logger

from app.config import config
from app.models.schema import VideoAspect
from app.services.visual_engine.cache import (
    compute_asset_hash,
    get_cached_asset,
    store_cached_asset,
)
from app.services.visual_engine.schema import VideoAsset


class BaseVideoProvider(ABC):
    """
    Abstract interface for AI video generation providers.
    """

    @abstractmethod
    def generate_text_to_video(
        self,
        prompt: str,
        negative_prompt: Optional[List[str]] = None,
        duration: float = 5.0,
        aspect: VideoAspect | str = "9:16",
        seed: Optional[int] = None,
        num_frames: Optional[int] = None,
        output_dir: str = "",
    ) -> VideoAsset:
        """
        Generates a video clip from a text prompt.
        """
        pass

    @abstractmethod
    def generate_image_to_video(
        self,
        image_path: str,
        prompt: str,
        negative_prompt: Optional[List[str]] = None,
        duration: float = 5.0,
        aspect: VideoAspect | str = "9:16",
        seed: Optional[int] = None,
        num_frames: Optional[int] = None,
        output_dir: str = "",
    ) -> VideoAsset:
        """
        Generates a video clip using an anchor image and motion prompt.
        """
        pass


class HuggingFaceProvider(BaseVideoProvider):
    """
    Hugging Face Inference Provider targeting Wan2.2 TI2V-5B.
    """

    def __init__(
        self,
        api_token: str = "",
        model: str = "Wan-AI/Wan2.2-TI2V-5B",
        base_url: str = "https://api-inference.huggingface.co/models",
        timeout: int = 120,
        max_retries: int = 2,
    ):
        # Read API token strictly from parameters, env, or configuration
        self.api_token = (
            api_token.strip()
            or os.environ.get("HF_TOKEN", "").strip()
            or os.environ.get("HUGGINGFACE_API_KEY", "").strip()
            or config.app.get("visual_engine", {}).get("hf_token", "").strip()
            or config.app.get("huggingface", {}).get("api_key", "").strip()
        )
        self.model = model.strip() or "Wan-AI/Wan2.2-TI2V-5B"
        self.base_url = base_url.rstrip("/")
        self.timeout = int(timeout)
        self.max_retries = int(max_retries)

    def _get_headers(self) -> Dict[str, str]:
        if not self.api_token:
            raise ValueError(
                "Hugging Face API token is required. Set HF_TOKEN environment variable "
                "or configure visual_engine.hf_token in config.toml."
            )
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "video/mp4, application/json",
        }

    def generate_text_to_video(
        self,
        prompt: str,
        negative_prompt: Optional[List[str]] = None,
        duration: float = 5.0,
        aspect: VideoAspect | str = "9:16",
        seed: Optional[int] = None,
        num_frames: Optional[int] = None,
        output_dir: str = "",
    ) -> VideoAsset:
        clean_prompt = prompt.strip()
        if not clean_prompt:
            raise ValueError("Text-to-video prompt cannot be empty.")

        actual_seed = seed if seed is not None else random.randint(1, 2**31 - 1)
        neg_list = [n.strip() for n in (negative_prompt or []) if n.strip()]

        # 1. Check Semantic Visual Cache
        asset_hash = compute_asset_hash(
            prompt=clean_prompt,
            negative_prompt=neg_list,
            duration=duration,
            aspect=str(aspect),
            seed=actual_seed,
            model=self.model,
            source_type="ai_t2v",
        )
        cached_asset = get_cached_asset(asset_hash, cache_dir=output_dir)
        if cached_asset:
            return cached_asset

        endpoint = f"{self.base_url}/{self.model}"
        payload: Dict[str, Any] = {
            "inputs": clean_prompt,
            "parameters": {
                "negative_prompt": ", ".join(neg_list) if neg_list else None,
                "guidance_scale": 6.0,
                "seed": actual_seed,
                "num_frames": num_frames or (81 if duration > 4.0 else 49),
            },
        }

        # Filter out None values from parameters
        payload["parameters"] = {k: v for k, v in payload["parameters"].items() if v is not None}

        logger.info(
            f"calling HuggingFace T2V ({self.model}): prompt='{clean_prompt[:60]}...', "
            f"seed={actual_seed}, dur={duration:.1f}s"
        )

        video_bytes = self._execute_with_retry(endpoint, payload)

        metadata = {
            "asset_id": asset_hash,
            "model": self.model,
            "provider": "huggingface",
            "source_type": "ai_t2v",
            "prompt_used": clean_prompt,
            "negative_prompt_used": neg_list,
            "duration": duration,
            "seed": actual_seed,
            "width": 1080 if "9:16" in str(aspect) or "portrait" in str(aspect) else 1920,
            "height": 1920 if "9:16" in str(aspect) or "portrait" in str(aspect) else 1080,
        }

        saved_path = store_cached_asset(
            asset_hash=asset_hash,
            video_bytes=video_bytes,
            metadata=metadata,
            cache_dir=output_dir,
        )

        return VideoAsset(
            asset_id=asset_hash,
            file_path=saved_path,
            duration=duration,
            width=metadata["width"],
            height=metadata["height"],
            source_type="ai_t2v",
            provider="huggingface",
            model=self.model,
            seed=actual_seed,
            prompt_used=clean_prompt,
            negative_prompt_used=neg_list,
            cached=False,
        )

    def generate_image_to_video(
        self,
        image_path: str,
        prompt: str,
        negative_prompt: Optional[List[str]] = None,
        duration: float = 5.0,
        aspect: VideoAspect | str = "9:16",
        seed: Optional[int] = None,
        num_frames: Optional[int] = None,
        output_dir: str = "",
    ) -> VideoAsset:
        if not image_path or not os.path.isfile(image_path):
            raise FileNotFoundError(f"Anchor image not found at: {image_path}")

        clean_prompt = prompt.strip()
        actual_seed = seed if seed is not None else random.randint(1, 2**31 - 1)
        neg_list = [n.strip() for n in (negative_prompt or []) if n.strip()]

        with open(image_path, "rb") as img_f:
            img_bytes = img_f.read()
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        img_hash = compute_asset_hash(prompt=img_b64[:100], duration=0, aspect="", model="")

        # 1. Check Semantic Visual Cache
        asset_hash = compute_asset_hash(
            prompt=clean_prompt,
            negative_prompt=neg_list,
            duration=duration,
            aspect=str(aspect),
            seed=actual_seed,
            model=self.model,
            source_type="ai_i2v",
            image_hash=img_hash,
        )
        cached_asset = get_cached_asset(asset_hash, cache_dir=output_dir)
        if cached_asset:
            return cached_asset

        endpoint = f"{self.base_url}/{self.model}"
        payload: Dict[str, Any] = {
            "inputs": {
                "prompt": clean_prompt,
                "image": f"data:image/jpeg;base64,{img_b64}",
            },
            "parameters": {
                "negative_prompt": ", ".join(neg_list) if neg_list else None,
                "guidance_scale": 6.0,
                "seed": actual_seed,
                "num_frames": num_frames or (81 if duration > 4.0 else 49),
            },
        }
        payload["parameters"] = {k: v for k, v in payload["parameters"].items() if v is not None}

        logger.info(
            f"calling HuggingFace I2V ({self.model}): image='{image_path}', "
            f"prompt='{clean_prompt[:50]}...', seed={actual_seed}"
        )

        video_bytes = self._execute_with_retry(endpoint, payload)

        metadata = {
            "asset_id": asset_hash,
            "model": self.model,
            "provider": "huggingface",
            "source_type": "ai_i2v",
            "prompt_used": clean_prompt,
            "negative_prompt_used": neg_list,
            "duration": duration,
            "seed": actual_seed,
            "width": 1080 if "9:16" in str(aspect) or "portrait" in str(aspect) else 1920,
            "height": 1920 if "9:16" in str(aspect) or "portrait" in str(aspect) else 1080,
        }

        saved_path = store_cached_asset(
            asset_hash=asset_hash,
            video_bytes=video_bytes,
            metadata=metadata,
            cache_dir=output_dir,
        )

        return VideoAsset(
            asset_id=asset_hash,
            file_path=saved_path,
            duration=duration,
            width=metadata["width"],
            height=metadata["height"],
            source_type="ai_i2v",
            provider="huggingface",
            model=self.model,
            seed=actual_seed,
            prompt_used=clean_prompt,
            negative_prompt_used=neg_list,
            cached=False,
        )

    def _execute_with_retry(self, endpoint: str, payload: Dict[str, Any]) -> bytes:
        """
        Executes HTTP request to Hugging Face with bounded retries and timeout.
        Never retries indefinitely.
        """
        headers = self._get_headers()
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )

                if response.status_code == 200:
                    content_type = response.headers.get("Content-Type", "")
                    if "video" in content_type or response.content.startswith(b"\x00\x00\x00") or len(response.content) > 1000:
                        return response.content
                    elif "json" in content_type:
                        # Some endpoints return a JSON payload with a direct video URL or b64
                        try:
                            data = response.json()
                            if isinstance(data, dict) and "video_url" in data:
                                dl_res = requests.get(data["video_url"], timeout=self.timeout)
                                if dl_res.status_code == 200:
                                    return dl_res.content
                            elif isinstance(data, dict) and "video" in data:
                                return base64.b64decode(data["video"])
                        except Exception:
                            pass
                        return response.content

                # Non-retryable client errors
                if response.status_code in (400, 401, 403, 404, 422):
                    err_msg = (
                        f"Hugging Face API returned HTTP {response.status_code} "
                        f"for model '{self.model}': {response.text[:300]}"
                    )
                    logger.error(err_msg)
                    raise RuntimeError(err_msg)

                # Retryable status codes (e.g. 500, 502, 503, 504)
                logger.warning(
                    f"Hugging Face request failed (attempt {attempt}/{self.max_retries}) "
                    f"HTTP {response.status_code}: {response.text[:150]}"
                )
                last_error = RuntimeError(f"HTTP {response.status_code}: {response.text[:150]}")

            except requests.Timeout as exc:
                logger.warning(f"Hugging Face request timed out ({self.timeout}s) on attempt {attempt}")
                last_error = exc
            except requests.RequestException as exc:
                logger.warning(f"Hugging Face network error on attempt {attempt}: {exc}")
                last_error = exc

            if attempt < self.max_retries:
                time.sleep(3.0 * attempt)

        raise RuntimeError(
            f"Hugging Face generation failed after {self.max_retries} attempts: {last_error}"
        )


class MockVideoProvider(BaseVideoProvider):
    """
    Mock AI Video Provider for zero-cost unit testing and offline CI pipelines.
    Generates synthetic valid video assets without making external API calls.
    """

    def generate_text_to_video(
        self,
        prompt: str,
        negative_prompt: Optional[List[str]] = None,
        duration: float = 5.0,
        aspect: VideoAspect | str = "9:16",
        seed: Optional[int] = None,
        num_frames: Optional[int] = None,
        output_dir: str = "",
    ) -> VideoAsset:
        clean_prompt = prompt.strip()
        actual_seed = seed or 42
        neg_list = negative_prompt or []

        asset_hash = compute_asset_hash(
            prompt=clean_prompt,
            negative_prompt=neg_list,
            duration=duration,
            aspect=str(aspect),
            seed=actual_seed,
            model="mock-wan-5b",
            source_type="mock",
        )

        metadata = {
            "asset_id": asset_hash,
            "model": "mock-wan-5b",
            "provider": "mock",
            "source_type": "mock",
            "prompt_used": clean_prompt,
            "negative_prompt_used": neg_list,
            "duration": duration,
            "seed": actual_seed,
            "width": 1080,
            "height": 1920,
        }

        # Create dummy mp4 bytes
        fake_video_bytes = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42\x00\x00\x00\x08free" + (b"\x00" * 512)
        saved_path = store_cached_asset(
            asset_hash=asset_hash,
            video_bytes=fake_video_bytes,
            metadata=metadata,
            cache_dir=output_dir,
        )

        return VideoAsset(
            asset_id=asset_hash,
            file_path=saved_path,
            duration=duration,
            width=1080,
            height=1920,
            source_type="mock",
            provider="mock",
            model="mock-wan-5b",
            seed=actual_seed,
            prompt_used=clean_prompt,
            negative_prompt_used=neg_list,
            cached=False,
        )

    def generate_image_to_video(
        self,
        image_path: str,
        prompt: str,
        negative_prompt: Optional[List[str]] = None,
        duration: float = 5.0,
        aspect: VideoAspect | str = "9:16",
        seed: Optional[int] = None,
        num_frames: Optional[int] = None,
        output_dir: str = "",
    ) -> VideoAsset:
        return self.generate_text_to_video(
            prompt=f"I2V: {prompt} (image={image_path})",
            negative_prompt=negative_prompt,
            duration=duration,
            aspect=aspect,
            seed=seed,
            num_frames=num_frames,
            output_dir=output_dir,
        )


def get_video_provider(
    provider_name: Optional[str] = None,
    app_config: Optional[dict] = None,
) -> BaseVideoProvider:
    """
    Factory function resolving the configured AI video generator.
    """
    cfg = app_config or config.app
    visual_cfg = cfg.get("visual_engine", {})
    name = (provider_name or visual_cfg.get("provider") or "huggingface").strip().lower()
    mode = str(visual_cfg.get("mode", "")).strip().lower()

    if name == "mock" or mode == "mock":
        return MockVideoProvider()

    if name == "huggingface":
        return HuggingFaceProvider(
            api_token=visual_cfg.get("hf_token", ""),
            model=visual_cfg.get("model", "Wan-AI/Wan2.2-TI2V-5B"),
        )

    raise ValueError(f"Unsupported visual engine AI video provider: '{name}'")
