"""
Unit tests for the AI Video Provider layer (Hugging Face Wan2.2 TI2V-5B and MockProvider).
All tests use mock requests so zero API credits are consumed.
"""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import requests

from app.models.schema import VideoAspect
from app.services.visual_engine import (
    BaseVideoProvider,
    HuggingFaceProvider,
    MockVideoProvider,
    VideoAsset,
    get_video_provider,
)


class TestAIProviderAbstraction(unittest.TestCase):
    def test_factory_resolves_mock_provider(self):
        provider = get_video_provider(provider_name="mock")
        self.assertIsInstance(provider, MockVideoProvider)
        self.assertIsInstance(provider, BaseVideoProvider)

    def test_factory_resolves_huggingface_provider(self):
        with patch.dict(os.environ, {"HF_TOKEN": "hf_test_token_123"}):
            provider = get_video_provider(provider_name="huggingface")
            self.assertIsInstance(provider, HuggingFaceProvider)
            self.assertEqual(provider.api_token, "hf_test_token_123")
            self.assertEqual(provider.model, "Wan-AI/Wan2.2-TI2V-5B")

    def test_factory_raises_for_unsupported_provider(self):
        with self.assertRaises(ValueError):
            get_video_provider(provider_name="unsupported_provider_xyz")


class TestHuggingFaceProvider(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.fake_mp4_bytes = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42" + (b"\x00" * 2048)

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_missing_api_token_raises(self):
        with patch.dict(os.environ, {"HF_TOKEN": ""}, clear=True):
            provider = HuggingFaceProvider(api_token="")
            with self.assertRaises(ValueError) as ctx:
                provider.generate_text_to_video(prompt="Scenic drone view of mountains")
            self.assertIn("Hugging Face API token is required", str(ctx.exception))

    def test_text_to_video_mocked_success(self):
        provider = HuggingFaceProvider(
            api_token="hf_mock_token",
            model="Wan-AI/Wan2.2-TI2V-5B",
            max_retries=1,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "video/mp4"}
        mock_response.content = self.fake_mp4_bytes

        with patch("requests.post", return_value=mock_response) as mock_post:
            asset = provider.generate_text_to_video(
                prompt="Cinematic drone shot of Kerala backwaters",
                negative_prompt=["temple", "snow", "mountains"],
                duration=6.5,
                aspect=VideoAspect.portrait,
                seed=8888,
                output_dir=self.temp_dir,
            )

            self.assertIsInstance(asset, VideoAsset)
            self.assertEqual(asset.source_type, "ai_t2v")
            self.assertEqual(asset.provider, "huggingface")
            self.assertEqual(asset.model, "Wan-AI/Wan2.2-TI2V-5B")
            self.assertEqual(asset.seed, 8888)
            self.assertFalse(asset.cached)
            self.assertTrue(os.path.exists(asset.file_path))

            # Verify request payload
            mock_post.assert_called_once()
            called_args, called_kwargs = mock_post.call_args
            self.assertIn("Wan-AI/Wan2.2-TI2V-5B", called_args[0])
            self.assertEqual(called_kwargs["headers"]["Authorization"], "Bearer hf_mock_token")
            payload = called_kwargs["json"]
            self.assertEqual(payload["inputs"], "Cinematic drone shot of Kerala backwaters")
            self.assertEqual(payload["parameters"]["seed"], 8888)
            self.assertIn("temple, snow, mountains", payload["parameters"]["negative_prompt"])
            self.assertEqual(payload["parameters"]["num_frames"], 81)

    def test_image_to_video_mocked_success(self):
        provider = HuggingFaceProvider(
            api_token="hf_mock_token",
            model="Wan-AI/Wan2.2-TI2V-5B",
            max_retries=1,
        )

        # Create dummy anchor image
        fake_img_path = os.path.join(self.temp_dir, "anchor.jpg")
        with open(fake_img_path, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + (b"\x00" * 500))

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "video/mp4"}
        mock_response.content = self.fake_mp4_bytes

        with patch("requests.post", return_value=mock_response) as mock_post:
            asset = provider.generate_image_to_video(
                image_path=fake_img_path,
                prompt="Slow camera pan across Taj Mahal facade",
                negative_prompt=["modern buildings"],
                duration=4.0,
                aspect="16:9",
                seed=9999,
                output_dir=self.temp_dir,
            )

            self.assertEqual(asset.source_type, "ai_i2v")
            self.assertEqual(asset.seed, 9999)
            self.assertTrue(os.path.exists(asset.file_path))

            mock_post.assert_called_once()
            called_args, called_kwargs = mock_post.call_args
            payload = called_kwargs["json"]
            self.assertIn("data:image/jpeg;base64,", payload["inputs"]["image"])
            self.assertEqual(payload["inputs"]["prompt"], "Slow camera pan across Taj Mahal facade")
            self.assertEqual(payload["parameters"]["seed"], 9999)
            self.assertEqual(payload["parameters"]["num_frames"], 49)

    def test_semantic_cache_hit_skips_network_call(self):
        provider = HuggingFaceProvider(
            api_token="hf_mock_token",
            model="Wan-AI/Wan2.2-TI2V-5B",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "video/mp4"}
        mock_response.content = self.fake_mp4_bytes

        with patch("requests.post", return_value=mock_response) as mock_post:
            # First call generates and caches
            asset1 = provider.generate_text_to_video(
                prompt="Futuristic quantum computer",
                duration=5.0,
                seed=42,
                output_dir=self.temp_dir,
            )
            self.assertFalse(asset1.cached)
            self.assertEqual(mock_post.call_count, 1)

            # Second identical call must hit cache without network request
            asset2 = provider.generate_text_to_video(
                prompt="Futuristic quantum computer",
                duration=5.0,
                seed=42,
                output_dir=self.temp_dir,
            )
            self.assertTrue(asset2.cached)
            self.assertEqual(mock_post.call_count, 1)  # Did not call requests.post again
            self.assertEqual(asset1.file_path, asset2.file_path)

    def test_bounded_retries_and_timeout(self):
        provider = HuggingFaceProvider(
            api_token="hf_mock_token",
            max_retries=2,
            timeout=5,
        )

        with (
            patch("requests.post", side_effect=requests.Timeout("Mock timeout")),
            patch("time.sleep") as mock_sleep,
        ):
            with self.assertRaises(RuntimeError) as ctx:
                provider.generate_text_to_video(
                    prompt="Retry test prompt",
                    output_dir=self.temp_dir,
                )
            self.assertIn("failed after 2 attempts", str(ctx.exception))
            mock_sleep.assert_called_once()

    def test_non_retryable_client_error(self):
        provider = HuggingFaceProvider(
            api_token="hf_mock_token",
            max_retries=3,
        )

        mock_err_response = MagicMock()
        mock_err_response.status_code = 401
        mock_err_response.text = '{"error":"Invalid username or password."}'

        with patch("requests.post", return_value=mock_err_response) as mock_post:
            with self.assertRaises(RuntimeError) as ctx:
                provider.generate_text_to_video(
                    prompt="Unauthorized test",
                    output_dir=self.temp_dir,
                )
            self.assertIn("HTTP 401", str(ctx.exception))
            self.assertEqual(mock_post.call_count, 1)  # Aborted immediately without retrying


class TestMockVideoProvider(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_mock_provider_generates_valid_assets(self):
        provider = MockVideoProvider()

        t2v_asset = provider.generate_text_to_video(
            prompt="Mock test scene",
            duration=4.5,
            output_dir=self.temp_dir,
        )
        self.assertIsInstance(t2v_asset, VideoAsset)
        self.assertEqual(t2v_asset.source_type, "mock")
        self.assertTrue(os.path.exists(t2v_asset.file_path))

        i2v_asset = provider.generate_image_to_video(
            image_path="test_img.jpg",
            prompt="Mock I2V scene",
            duration=5.0,
            output_dir=self.temp_dir,
        )
        self.assertIsInstance(i2v_asset, VideoAsset)
        self.assertTrue(os.path.exists(i2v_asset.file_path))


if __name__ == "__main__":
    unittest.main()
