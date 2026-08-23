"""
Unit tests for the Semantic Visual Engine Scene Planner.
"""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from app.config import config
from app.models.schema import VideoParams
from app.services.task import plan_visual_scenes_if_enabled
from app.services.visual_engine import (
    ScenePlan,
    ScenePlanningResult,
    VisualIntent,
    plan_scenes,
)
from app.services.visual_engine.scene_planner import (
    _distribute_timestamps,
    _parse_llm_json_response,
    _split_into_sentences,
)


class TestScenePlannerSchema(unittest.TestCase):
    def test_visual_intent_defaults(self):
        intent = VisualIntent(subject="Beach sunset")
        self.assertEqual(intent.subject, "Beach sunset")
        self.assertEqual(intent.location, "")
        self.assertEqual(intent.objects, [])
        self.assertEqual(intent.style, "realistic documentary footage")
        self.assertEqual(intent.visual_priority, "high")
        self.assertFalse(intent.factual_visual)

    def test_scene_plan_creation(self):
        intent = VisualIntent(
            subject="Kerala Backwaters",
            location="Alappuzha, Kerala, India",
            objects=["traditional houseboat", "tropical waterways"],
            action="houseboat gliding slowly through backwaters",
            style="realistic cinematic documentary footage, 4k",
            stock_queries=[
                "Alappuzha Kerala backwaters houseboat",
                "Kerala backwater houseboat",
            ],
            ai_prompt="Cinematic realistic aerial footage of Kerala backwaters...",
            negative_prompt=["Ganges", "Varanasi", "temple", "snow", "mountains"],
            visual_priority="high",
            factual_visual=True,
        )
        scene = ScenePlan(
            scene_id="scene_001",
            scene_index=1,
            narration="Kerala is famous for its extensive network of backwaters.",
            start_time=0.0,
            end_time=6.8,
            duration_seconds=6.8,
            visual_intent=intent,
        )
        self.assertEqual(scene.scene_id, "scene_001")
        self.assertEqual(scene.visual_intent.location, "Alappuzha, Kerala, India")
        self.assertTrue(scene.visual_intent.factual_visual)
        self.assertIn("Ganges", scene.visual_intent.negative_prompt)


class TestScenePlannerCore(unittest.TestCase):
    def test_split_into_sentences(self):
        text = "Hello world! This is a test. Are you ready? Yes, indeed."
        sentences = _split_into_sentences(text)
        self.assertEqual(len(sentences), 4)
        self.assertEqual(sentences[0], "Hello world!")
        self.assertEqual(sentences[1], "This is a test.")

    def test_split_into_sentences_multilingual(self):
        zh_text = "这是第一个场景。这是第二个场景！这是第三个场景？"
        sentences = _split_into_sentences(zh_text)
        self.assertEqual(len(sentences), 3)
        self.assertEqual(sentences[0], "这是第一个场景。")
        self.assertEqual(sentences[1], "这是第二个场景！")
        self.assertEqual(sentences[2], "这是第三个场景？")

    def test_distribute_timestamps(self):
        scenes = [
            ScenePlan(
                scene_id="1",
                scene_index=1,
                narration="Short sentence.",
                visual_intent=VisualIntent(subject="A"),
            ),
            ScenePlan(
                scene_id="2",
                scene_index=2,
                narration="This is a substantially longer narration sentence with more words.",
                visual_intent=VisualIntent(subject="B"),
            ),
        ]
        total_duration = 20.0
        timed = _distribute_timestamps(scenes, total_duration)

        self.assertEqual(len(timed), 2)
        self.assertEqual(timed[0].start_time, 0.0)
        self.assertEqual(timed[-1].end_time, 20.0)
        self.assertAlmostEqual(timed[0].duration_seconds + timed[1].duration_seconds, 20.0, delta=0.1)
        self.assertGreater(timed[1].duration_seconds, timed[0].duration_seconds)

    def test_parse_llm_json_response_with_markdown_fences(self):
        raw = """Here is the scene plan:
```json
[
  {
    "narration": "Goa is famous for its vibrant beaches.",
    "visual_intent": {
      "subject": "Goa beach",
      "location": "Goa, India",
      "objects": ["sandy beach", "waves"],
      "action": "waves rolling onto beach",
      "style": "cinematic documentary 4k",
      "stock_queries": ["Goa beach sunset", "Arabian sea beach"],
      "ai_prompt": "Cinematic 4k footage of Goa beach coastline",
      "negative_prompt": ["temple", "mountains", "snow"],
      "visual_priority": "high",
      "factual_visual": true
    }
  }
]
```
Enjoy your video!
"""
        parsed = _parse_llm_json_response(raw)
        self.assertIsNotNone(parsed)
        self.assertIsInstance(parsed, list)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["visual_intent"]["subject"], "Goa beach")

    def test_plan_scenes_with_mocked_llm_success(self):
        fake_llm_response = json.dumps([
            {
                "narration": "Artificial intelligence is changing how we work.",
                "visual_intent": {
                    "subject": "AI digital technology",
                    "location": "",
                    "objects": ["neural network", "digital interfaces"],
                    "action": "glowing data streams flowing",
                    "style": "high-tech cinematic 4k",
                    "stock_queries": ["AI technology", "neural network"],
                    "ai_prompt": "Futuristic neural network with flowing lights",
                    "negative_prompt": ["blurry", "low resolution"],
                    "visual_priority": "high",
                    "factual_visual": False,
                },
            },
            {
                "narration": "ChatGPT drafts emails and writes code in seconds.",
                "visual_intent": {
                    "subject": "Coding and email automation",
                    "location": "",
                    "objects": ["laptop", "code on screen"],
                    "action": "typing code rapidly",
                    "style": "modern office documentary",
                    "stock_queries": ["developer coding laptop", "modern office productivity"],
                    "ai_prompt": "Close-up of clean code on high-res laptop screen",
                    "negative_prompt": ["vintage computer", "messy desk"],
                    "visual_priority": "medium",
                    "factual_visual": False,
                },
            },
        ])

        with patch("app.services.llm._generate_response", return_value=fake_llm_response):
            result = plan_scenes(
                video_script="Artificial intelligence is changing how we work. ChatGPT drafts emails and writes code in seconds.",
                total_duration=15.0,
                language="en-US",
            )

            self.assertEqual(result.status, "success")
            self.assertFalse(result.fallback_used)
            self.assertEqual(len(result.scenes), 2)
            self.assertEqual(result.total_duration, 15.0)
            self.assertEqual(result.scenes[0].scene_id, "scene_001")
            self.assertEqual(result.scenes[0].start_time, 0.0)
            self.assertEqual(result.scenes[1].end_time, 15.0)
            self.assertEqual(result.scenes[0].visual_intent.subject, "AI digital technology")

    def test_plan_scenes_fallback_on_invalid_json(self):
        with patch("app.services.llm._generate_response", return_value="Not a JSON response at all!"):
            result = plan_scenes(
                video_script="Kerala is famous for backwaters. Goa is known for sandy beaches.",
                total_duration=12.0,
            )

            self.assertEqual(result.status, "fallback")
            self.assertTrue(result.fallback_used)
            self.assertGreaterEqual(len(result.scenes), 2)
            self.assertEqual(result.total_duration, 12.0)
            self.assertEqual(result.scenes[0].start_time, 0.0)
            self.assertEqual(result.scenes[-1].end_time, 12.0)

    def test_plan_scenes_fallback_on_error_response(self):
        with patch("app.services.llm._generate_response", return_value="Error: Connection failed"):
            result = plan_scenes(
                video_script="First sentence here. Second sentence here.",
                total_duration=10.0,
            )
            self.assertEqual(result.status, "fallback")
            self.assertTrue(result.fallback_used)
            self.assertEqual(len(result.scenes), 2)

    def test_plan_scenes_fallback_on_exception(self):
        with patch("app.services.llm._generate_response", side_effect=RuntimeError("API timeout")):
            result = plan_scenes(
                video_script="First sentence. Second sentence.",
                total_duration=8.0,
            )
            self.assertEqual(result.status, "fallback")
            self.assertTrue(result.fallback_used)

    def test_plan_scenes_empty_script(self):
        result = plan_scenes(video_script="")
        self.assertEqual(result.status, "failed")
        self.assertEqual(len(result.scenes), 0)

    def test_plan_scenes_benchmark_domains(self):
        domains = [
            {
                "name": "Kerala",
                "script": "Kerala is famous for serene backwaters and houseboats in Alappuzha.",
                "duration": 14.5,
                "factual": True,
                "location": "Alappuzha, Kerala, India",
                "negatives": ["temple", "Ganges", "Varanasi", "snow", "mountains"],
            },
            {
                "name": "Goa",
                "script": "Goa offers pristine beaches along the Arabian Sea and vibrant tourism.",
                "duration": 12.0,
                "factual": True,
                "location": "Goa, India",
                "negatives": ["snow", "mountains", "temple", "desert"],
            },
            {
                "name": "Taj Mahal",
                "script": "The Taj Mahal in Agra stands as a world-renowned masterpiece of Mughal architecture.",
                "duration": 11.2,
                "factual": True,
                "location": "Agra, India",
                "negatives": ["modern skyscrapers", "beach", "traffic"],
            },
            {
                "name": "Generic Technology",
                "script": "Artificial intelligence and cloud computing process data in milliseconds.",
                "duration": 10.0,
                "factual": False,
                "location": "",
                "negatives": ["vintage", "blurry", "paper"],
            },
            {
                "name": "Funny Meme",
                "script": "When you deploy to production on Friday at 5 PM and the whole server crashes.",
                "duration": 9.5,
                "factual": False,
                "location": "",
                "negatives": ["serious documentary", "depressing"],
            },
        ]

        for item in domains:
            fake_response = json.dumps([
                {
                    "narration": item["script"],
                    "visual_intent": {
                        "subject": f"Visual for {item['name']}",
                        "location": item["location"],
                        "objects": ["primary object"],
                        "action": "cinematic motion",
                        "style": "cinematic 4k",
                        "stock_queries": [f"{item['name']} footage"],
                        "ai_prompt": f"Cinematic shot of {item['name']}",
                        "negative_prompt": item["negatives"],
                        "visual_priority": "high",
                        "factual_visual": item["factual"],
                    },
                }
            ])

            with patch("app.services.llm._generate_response", return_value=fake_response):
                res = plan_scenes(
                    video_script=item["script"],
                    total_duration=item["duration"],
                )
                self.assertEqual(res.status, "success", f"Failed for domain {item['name']}")
                self.assertEqual(len(res.scenes), 1)
                self.assertEqual(res.scenes[0].visual_intent.factual_visual, item["factual"])
                self.assertEqual(res.scenes[0].visual_intent.location, item["location"])
                self.assertEqual(res.scenes[0].duration_seconds, item["duration"])
                self.assertEqual(res.scenes[0].start_time, 0.0)
                self.assertEqual(res.scenes[0].end_time, item["duration"])



class TestScenePlannerTaskIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_plan_visual_scenes_disabled_by_default(self):
        params = VideoParams(video_subject="Test", video_script="Hello world")
        with patch.dict(config.app, {"visual_engine": {"enabled": False}}):
            result = plan_visual_scenes_if_enabled("task-123", params, "Hello world", 10.0)
            self.assertIsNone(result)

    def test_plan_visual_scenes_writes_plan_when_enabled(self):
        params = VideoParams(video_subject="Test", video_script="Hello world")
        task_id = "task-test-plan"
        task_workspace = os.path.join(self.temp_dir, task_id)
        os.makedirs(task_workspace, exist_ok=True)

        fake_plan_result = ScenePlanningResult(
            scenes=[
                ScenePlan(
                    scene_id="scene_001",
                    scene_index=1,
                    narration="Hello world",
                    start_time=0.0,
                    end_time=5.0,
                    duration_seconds=5.0,
                    visual_intent=VisualIntent(subject="Earth from space"),
                )
            ],
            total_duration=5.0,
            status="success",
            fallback_used=False,
        )

        with (
            patch.dict(config.app, {"visual_engine": {"enabled": True}}),
            patch("app.utils.utils.task_dir", return_value=task_workspace),
            patch("app.services.visual_engine.plan_scenes", return_value=fake_plan_result),
        ):
            result = plan_visual_scenes_if_enabled(task_id, params, "Hello world", 5.0)
            self.assertIsNotNone(result)
            self.assertEqual(len(result.scenes), 1)

            plan_file = os.path.join(task_workspace, "scene_plan.json")
            self.assertTrue(os.path.exists(plan_file))
            with open(plan_file, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
            self.assertEqual(saved_data["status"], "success")
            self.assertEqual(saved_data["scenes"][0]["scene_id"], "scene_001")


if __name__ == "__main__":
    unittest.main()
