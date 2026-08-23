"""
Unit tests for standardized Visual Logging, Hashtag enrichment, and Secrets configuration.
"""
import os
import tempfile
import unittest
from unittest.mock import patch

from app.models.schema import VideoAspect
from app.services.visual_engine import (
    MockVideoProvider,
    ScenePlan,
    ScenePlanningResult,
    VisualIntent,
    acquire_scene_materials,
)
from scripts.apply_secrets import REPLACEMENTS


class TestVisualLoggingAndMetadata(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.task_id = "test-logging-task"
        self.task_dir = os.path.join(self.temp_dir, self.task_id)
        os.makedirs(self.task_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_visual_logging_format_emitted(self):
        scene = ScenePlan(
            scene_id="scene_001",
            scene_index=1,
            narration="Exploring artificial intelligence breakthroughs.",
            duration_seconds=4.0,
            visual_intent=VisualIntent(
                subject="AI technology neural chip",
                factual_visual=False,
                ai_prompt="Futuristic quantum neural chip glow",
            ),
        )
        plan = ScenePlanningResult(scenes=[scene], total_duration=4.0)
        mock_ai = MockVideoProvider()

        with (
            patch("app.services.visual_engine.engine.retrieve_stock_for_scene", return_value=None),
            patch("app.services.visual_engine.engine.get_video_provider", return_value=mock_ai),
            patch("loguru.logger.info") as mock_logger_info,
        ):
            results = acquire_scene_materials(
                task_id=self.task_id,
                scene_plan=plan,
                video_aspect=VideoAspect.portrait,
                material_directory=self.task_dir,
                app_config={"visual_engine": {"enabled": True, "mode": "hybrid"}},
            )

            self.assertEqual(len(results), 1)
            # Verify structured log line "[VISUAL] Scene 1 → Wan2.2 → generated" or "[VISUAL] Scene 1 → ..."
            logged_messages = [call.args[0] for call in mock_logger_info.call_args_list if call.args]
            visual_logs = [msg for msg in logged_messages if msg.startswith("[VISUAL]")]
            self.assertTrue(len(visual_logs) > 0)
            self.assertIn("[VISUAL] Scene 1", visual_logs[0])

    def test_apply_secrets_includes_hf_token(self):
        with patch.dict(os.environ, {"HF_TOKEN": "hf_secret_token_abc"}):
            hf_repl = REPLACEMENTS.get(r'^hf_token = ""$')
            self.assertIsNotNone(hf_repl)
            replaced_val = hf_repl() if callable(hf_repl) else hf_repl
            self.assertIn('hf_token = "hf_secret_token_abc"', replaced_val)

            enabled_repl = REPLACEMENTS.get(r'^enabled = false$')
            self.assertIsNotNone(enabled_repl)
            self.assertIn('enabled = true', enabled_repl() if callable(enabled_repl) else enabled_repl)


if __name__ == "__main__":
    unittest.main()
