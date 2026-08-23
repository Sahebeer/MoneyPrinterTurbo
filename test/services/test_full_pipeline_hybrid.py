"""
End-to-End Pipeline Integration tests for the Semantic Visual Engine.
Verifies integration with task._run_pipeline(), audio, subtitles, scene planning,
and video composition in both legacy and hybrid modes.
"""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from app.config import config
from app.models import const
from app.models.schema import VideoAspect, VideoConcatMode, VideoParams
from app.services import state as sm
from app.services.task import _run_pipeline
from app.services.visual_engine import (
    ScenePlan,
    ScenePlanningResult,
    VisualIntent,
)


class TestFullPipelineHybrid(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.task_id = "test-full-pipeline-task"
        self.task_dir = os.path.join(self.temp_dir, self.task_id)
        os.makedirs(self.task_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_legacy_pipeline_when_visual_engine_disabled(self):
        """
        Regression test: When visual engine is disabled, the pipeline executes
        the standard legacy path with standard terms and download_videos.
        """
        params = VideoParams(
            video_subject="Legacy Top 5 AI Tools",
            video_script="Artificial intelligence is transforming modern productivity.",
            video_source="pexels",
            visual_engine_enabled=False,
            video_count=1,
            subtitle_enabled=False,
        )

        mock_stock_video = os.path.join(self.task_dir, "legacy_stock.mp4")
        with open(mock_stock_video, "wb") as f:
            f.write(b"legacy stock mp4 bytes")

        mock_audio_file = os.path.join(self.task_dir, "audio.mp3")
        with open(mock_audio_file, "wb") as f:
            f.write(b"fake audio mp3 bytes")

        with (
            patch.dict(config.app, {"visual_engine": {"enabled": False}}),
            patch("app.utils.utils.task_dir", return_value=self.task_dir),
            patch("app.utils.utils.check_ffmpeg_ready", return_value=True),
            patch("app.services.task.generate_script", return_value=params.video_script),
            patch("app.services.task.generate_terms", return_value=["AI tools", "productivity"]),
            patch("app.services.task.generate_audio", return_value=(mock_audio_file, 8.0, None)),
            patch("app.services.task.generate_subtitle", return_value=""),
            patch("app.services.material.download_videos", return_value=[mock_stock_video]),
            patch("app.services.video.combine_videos") as mock_combine,
            patch("app.services.video.generate_video", return_value=True) as mock_gen_vid,
        ):
            res = _run_pipeline(self.task_id, params, stop_at="video")
            self.assertIsNotNone(res)
            self.assertEqual(res.get("materials"), [mock_stock_video])
            self.assertEqual(len(res.get("videos")), 1)

            task_record = sm.state.get_task(self.task_id)
            self.assertEqual(task_record.get("state"), const.TASK_STATE_COMPLETE)
            mock_combine.assert_called_once()
            mock_gen_vid.assert_called_once()

    def test_hybrid_pipeline_with_four_scenes(self):
        """
        Integration test: Runs a 4-scene video through the Semantic Visual Engine:
        Scene 1: Kerala backwaters (Factual)
        Scene 2: Goa beach (Factual)
        Scene 3: Taj Mahal (Factual)
        Scene 4: Enterprise AI (Conceptual)
        Verifies scene_plan.json generation, sequential clip ordering, audio, subtitle, and final video composition.
        """
        script_text = (
            "Kerala is famous for serene backwaters. "
            "Goa attracts tourists with sunny beaches. "
            "The Taj Mahal in Agra stands in magnificent white marble. "
            "Modern artificial intelligence powers enterprise workflows."
        )

        params = VideoParams(
            video_subject="Incredible India & Future of AI",
            video_script=script_text,
            video_source="pexels",
            video_aspect=VideoAspect.portrait,
            visual_engine_enabled=True,
            video_count=1,
            subtitle_enabled=True,
        )

        mock_audio_file = os.path.join(self.task_dir, "audio.mp3")
        with open(mock_audio_file, "wb") as f:
            f.write(b"fake audio mp3 bytes")

        mock_subtitle_file = os.path.join(self.task_dir, "subtitle.srt")
        with open(mock_subtitle_file, "w", encoding="utf-8") as f:
            f.write("1\n00:00:00,000 --> 00:00:16,000\nIncredible India & AI\n")

        # 4 Mock Scene Plans
        scenes = [
            ScenePlan(
                scene_id="scene_001",
                scene_index=1,
                narration="Kerala is famous for serene backwaters.",
                start_time=0.0,
                end_time=4.0,
                duration_seconds=4.0,
                visual_intent=VisualIntent(
                    subject="Kerala houseboat backwaters",
                    location="Kerala, India",
                    factual_visual=True,
                    stock_queries=["Kerala backwaters houseboat"],
                ),
            ),
            ScenePlan(
                scene_id="scene_002",
                scene_index=2,
                narration="Goa attracts tourists with sunny beaches.",
                start_time=4.0,
                end_time=8.0,
                duration_seconds=4.0,
                visual_intent=VisualIntent(
                    subject="Goa sunny beach",
                    location="Goa, India",
                    factual_visual=True,
                    stock_queries=["Goa beach Arabian sea"],
                ),
            ),
            ScenePlan(
                scene_id="scene_003",
                scene_index=3,
                narration="The Taj Mahal in Agra stands in magnificent white marble.",
                start_time=8.0,
                end_time=12.0,
                duration_seconds=4.0,
                visual_intent=VisualIntent(
                    subject="Taj Mahal Agra",
                    location="Agra, India",
                    factual_visual=True,
                    stock_queries=["Taj Mahal Agra sunrise"],
                ),
            ),
            ScenePlan(
                scene_id="scene_004",
                scene_index=4,
                narration="Modern artificial intelligence powers enterprise workflows.",
                start_time=12.0,
                end_time=16.0,
                duration_seconds=4.0,
                visual_intent=VisualIntent(
                    subject="Enterprise AI data analytics",
                    factual_visual=False,
                    stock_queries=["AI enterprise productivity"],
                ),
            ),
        ]
        four_scene_plan = ScenePlanningResult(scenes=scenes, total_duration=16.0, status="success")

        # Mock 4 scene video files
        scene_files = []
        for s in scenes:
            fp = os.path.join(self.task_dir, f"clip_{s.scene_id}.mp4")
            with open(fp, "wb") as f:
                f.write(b"scene mp4 bytes")
            scene_files.append(fp)

        with (
            patch.dict(config.app, {"visual_engine": {"enabled": True, "mode": "hybrid"}}),
            patch("app.utils.utils.task_dir", return_value=self.task_dir),
            patch("app.utils.utils.check_ffmpeg_ready", return_value=True),
            patch("app.services.task.generate_script", return_value=script_text),
            patch("app.services.task.generate_terms", return_value=["India", "AI"]),
            patch("app.services.task.generate_audio", return_value=(mock_audio_file, 16.0, MagicMock())),
            patch("app.services.task.generate_subtitle", return_value=mock_subtitle_file),
            patch("app.services.visual_engine.plan_scenes", return_value=four_scene_plan),
            patch("app.services.visual_engine.acquire_scene_materials", return_value=scene_files),
            patch("app.services.video.combine_videos") as mock_combine,
            patch("app.services.video.generate_video", return_value=True) as mock_gen_vid,
        ):
            res = _run_pipeline(self.task_id, params, stop_at="video")

            self.assertIsNotNone(res)
            # Check materials list matches the 4 scene video clips
            self.assertEqual(res.get("materials"), scene_files)
            self.assertEqual(len(res.get("materials")), 4)

            task_record = sm.state.get_task(self.task_id)
            self.assertEqual(task_record.get("state"), const.TASK_STATE_COMPLETE)
            self.assertEqual(task_record.get("progress"), 100)

            # Verify combine_videos called with sequential mode and the 4 scene clips
            mock_combine.assert_called_once()
            called_kwargs = mock_combine.call_args.kwargs
            self.assertEqual(called_kwargs["video_paths"], scene_files)
            self.assertEqual(called_kwargs["video_concat_mode"], VideoConcatMode.sequential)

            # Verify generate_video called with subtitle and audio
            mock_gen_vid.assert_called_once()
            gen_kwargs = mock_gen_vid.call_args.kwargs
            self.assertEqual(gen_kwargs["audio_path"], mock_audio_file)
            self.assertEqual(gen_kwargs["subtitle_path"], mock_subtitle_file)


if __name__ == "__main__":
    unittest.main()
