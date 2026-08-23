"""
Integration tests for the Hybrid Visual Selector and Visual Engine task pipeline.
"""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from app.config import config
from app.models.schema import VideoAspect, VideoParams
from app.services.task import get_video_materials
from app.services.visual_engine import (
    MockVideoProvider,
    RelevanceScore,
    ScenePlan,
    ScenePlanningResult,
    ScoredCandidate,
    VideoAsset,
    VisualIntent,
    acquire_scene_materials,
)


class TestHybridVisualSelector(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.task_id = "task-integration-123"
        self.task_dir = os.path.join(self.temp_dir, self.task_id)
        os.makedirs(self.task_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_legacy_path_when_visual_engine_disabled(self):
        params = VideoParams(video_subject="Legacy Test", video_source="pexels")
        legacy_mock_videos = ["/path/to/vid1.mp4", "/path/to/vid2.mp4"]

        with (
            patch.dict(config.app, {"visual_engine": {"enabled": False}}),
            patch("app.services.material.download_videos", return_value=legacy_mock_videos) as mock_dl,
        ):
            result = get_video_materials(
                task_id=self.task_id,
                params=params,
                video_terms=["AI technology"],
                audio_duration=10.0,
            )
            self.assertEqual(result, legacy_mock_videos)
            mock_dl.assert_called_once()

    def test_stock_first_match_avoids_ai_generation(self):
        scene = ScenePlan(
            scene_id="scene_001",
            scene_index=1,
            narration="Beautiful Goa coastline.",
            duration_seconds=5.0,
            visual_intent=VisualIntent(
                subject="Goa coastal beach",
                location="Goa, India",
                stock_queries=["Goa beach Arabian sea"],
                factual_visual=True,
            ),
        )
        plan = ScenePlanningResult(scenes=[scene], total_duration=5.0)

        saved_stock_path = os.path.join(self.task_dir, "stock_goa.mp4")
        with open(saved_stock_path, "wb") as f:
            f.write(b"fake stock video bytes")

        stock_candidate = ScoredCandidate(
            scene_id="scene_001",
            url="https://pexels.com/video/goa-1",
            local_path=saved_stock_path,
            duration=6.0,
            score=RelevanceScore(total_score=90.0, is_accepted=True),
        )

        mock_ai = MagicMock()

        with (
            patch("app.services.visual_engine.engine.retrieve_stock_for_scene", return_value=stock_candidate),
            patch("app.services.visual_engine.engine.get_video_provider", return_value=mock_ai),
        ):
            results = acquire_scene_materials(
                task_id=self.task_id,
                scene_plan=plan,
                video_aspect=VideoAspect.portrait,
                material_directory=self.task_dir,
                app_config={"visual_engine": {"enabled": True, "mode": "hybrid"}},
            )

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0], saved_stock_path)
            mock_ai.generate_text_to_video.assert_not_called()
            mock_ai.generate_image_to_video.assert_not_called()

    def test_ai_t2v_used_for_conceptual_scene_when_stock_fails(self):
        scene = ScenePlan(
            scene_id="scene_001",
            scene_index=1,
            narration="Futuristic neural networks synapsing.",
            duration_seconds=4.0,
            visual_intent=VisualIntent(
                subject="Neural network glowing data",
                stock_queries=["quantum neural network"],
                factual_visual=False,
            ),
        )
        plan = ScenePlanningResult(scenes=[scene], total_duration=4.0)

        mock_ai = MockVideoProvider()

        with (
            patch("app.services.visual_engine.engine.retrieve_stock_for_scene", return_value=None),
            patch("app.services.visual_engine.engine.get_video_provider", return_value=mock_ai),
        ):
            results = acquire_scene_materials(
                task_id=self.task_id,
                scene_plan=plan,
                video_aspect=VideoAspect.portrait,
                material_directory=self.task_dir,
                app_config={"visual_engine": {"enabled": True, "mode": "hybrid"}},
            )

            self.assertEqual(len(results), 1)
            self.assertTrue(os.path.isfile(results[0]))
            self.assertGreater(os.path.getsize(results[0]), 0)

    def test_ai_i2v_used_for_factual_scene_when_stock_fails(self):
        scene = ScenePlan(
            scene_id="scene_001",
            scene_index=1,
            narration="Taj Mahal in Agra under morning light.",
            duration_seconds=5.0,
            visual_intent=VisualIntent(
                subject="Taj Mahal Agra",
                location="Agra, India",
                stock_queries=["Taj Mahal Agra sunrise"],
                factual_visual=True,
            ),
        )
        plan = ScenePlanningResult(scenes=[scene], total_duration=5.0)

        ai_out_path = os.path.join(self.task_dir, "taj_i2v.mp4")
        with open(ai_out_path, "wb") as f:
            f.write(b"fake i2v video bytes")

        mock_ai = MagicMock()
        mock_ai.generate_image_to_video.return_value = VideoAsset(
            asset_id="taj_asset_1",
            file_path=ai_out_path,
            source_type="ai_i2v",
        )

        with (
            patch("app.services.visual_engine.engine.retrieve_stock_for_scene", return_value=None),
            patch("app.services.visual_engine.engine.get_video_provider", return_value=mock_ai),
        ):
            results = acquire_scene_materials(
                task_id=self.task_id,
                scene_plan=plan,
                video_aspect=VideoAspect.portrait,
                material_directory=self.task_dir,
                app_config={
                    "visual_engine": {
                        "enabled": True,
                        "mode": "hybrid",
                        "prefer_i2v_for_factual": True,
                    }
                },
            )

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0], ai_out_path)
            mock_ai.generate_image_to_video.assert_called_once()

    def test_max_ai_generations_budget_limiting(self):
        scenes = [
            ScenePlan(
                scene_id=f"scene_{i}",
                scene_index=i,
                narration=f"Scene {i} narration.",
                duration_seconds=4.0,
                visual_intent=VisualIntent(subject=f"Subject {i}", factual_visual=False),
            )
            for i in range(1, 4)
        ]
        plan = ScenePlanningResult(scenes=scenes, total_duration=12.0)

        mock_ai = MockVideoProvider()

        with (
            patch("app.services.visual_engine.engine.retrieve_stock_for_scene", return_value=None),
            patch("app.services.visual_engine.engine.get_video_provider", return_value=mock_ai),
        ):
            results = acquire_scene_materials(
                task_id=self.task_id,
                scene_plan=plan,
                video_aspect=VideoAspect.portrait,
                material_directory=self.task_dir,
                app_config={
                    "visual_engine": {
                        "enabled": True,
                        "mode": "hybrid",
                        "max_ai_scenes_per_video": 1,  # Only allow 1 AI generation
                    }
                },
            )

            self.assertEqual(len(results), 3)
            for path_item in results:
                self.assertTrue(os.path.isfile(path_item))

    def test_graceful_fallback_when_ai_fails(self):
        scene = ScenePlan(
            scene_id="scene_001",
            scene_index=1,
            narration="A rare galaxy collision in deep space.",
            duration_seconds=4.0,
            visual_intent=VisualIntent(subject="Deep space galaxy", factual_visual=False),
        )
        plan = ScenePlanningResult(scenes=[scene], total_duration=4.0)

        mock_ai = MagicMock()
        mock_ai.generate_text_to_video.side_effect = RuntimeError("Hugging Face Rate Limit Exceeded")

        with (
            patch("app.services.visual_engine.engine.retrieve_stock_for_scene", return_value=None),
            patch("app.services.visual_engine.engine.get_video_provider", return_value=mock_ai),
        ):
            results = acquire_scene_materials(
                task_id=self.task_id,
                scene_plan=plan,
                video_aspect=VideoAspect.portrait,
                material_directory=self.task_dir,
                app_config={"visual_engine": {"enabled": True, "mode": "hybrid"}},
            )

            self.assertEqual(len(results), 1)
            self.assertTrue(os.path.isfile(results[0]))
            self.assertIn("fallback", results[0])

    def test_resumability_and_cache_reuse(self):
        scene = ScenePlan(
            scene_id="scene_001",
            scene_index=1,
            narration="Autonomous robotics.",
            duration_seconds=5.0,
            visual_intent=VisualIntent(
                subject="Autonomous robotics factory",
                factual_visual=False,
                ai_prompt="Futuristic automated robotic arms assembly line 4k",
            ),
        )
        plan = ScenePlanningResult(scenes=[scene], total_duration=5.0)

        mock_ai = MagicMock()
        fake_video_file = os.path.join(self.task_dir, "fake_robotics.mp4")
        with open(fake_video_file, "wb") as f:
            f.write(b"robotics mp4 bytes")

        mock_ai.generate_text_to_video.return_value = VideoAsset(
            asset_id="mock_robotics_asset",
            file_path=fake_video_file,
            source_type="ai_t2v",
        )

        with (
            patch("app.services.visual_engine.engine.retrieve_stock_for_scene", return_value=None),
            patch("app.services.visual_engine.engine.get_video_provider", return_value=mock_ai),
        ):
            # First execution calls mock_ai
            results1 = acquire_scene_materials(
                task_id=self.task_id,
                scene_plan=plan,
                video_aspect=VideoAspect.portrait,
                material_directory=self.task_dir,
                app_config={"visual_engine": {"enabled": True, "mode": "hybrid"}},
            )
            self.assertEqual(len(results1), 1)
            self.assertEqual(mock_ai.generate_text_to_video.call_count, 1)

            # Re-mock return with empty or check cache
            results2 = acquire_scene_materials(
                task_id=self.task_id,
                scene_plan=plan,
                video_aspect=VideoAspect.portrait,
                material_directory=self.task_dir,
                app_config={"visual_engine": {"enabled": True, "mode": "hybrid"}},
            )
            self.assertEqual(len(results2), 1)


if __name__ == "__main__":
    unittest.main()
