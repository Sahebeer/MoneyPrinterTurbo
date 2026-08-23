"""
Unit tests for the Semantic Stock Retrieval and Search Scorer modules.
"""
import os
import tempfile
import unittest
from unittest.mock import patch

from app.models.schema import MaterialInfo, VideoAspect
from app.services.visual_engine import (
    ScenePlan,
    VisualIntent,
    retrieve_stock_for_scene,
    score_candidate,
)


class TestSearchScorer(unittest.TestCase):
    def test_kerala_vs_generic_india(self):
        intent = VisualIntent(
            subject="Alappuzha Kerala houseboat on tranquil backwaters",
            location="Alappuzha, Kerala, India",
            objects=["houseboat", "palm trees", "canal"],
            action="houseboat gliding on calm waters",
            stock_queries=["Alappuzha Kerala backwaters houseboat", "Kerala backwaters"],
            negative_prompt=["Ganges", "Varanasi", "temple", "snow", "mountains"],
            factual_visual=True,
        )

        # Irrelevant / generic candidate with forbidden terms
        bad_candidate = MaterialInfo(
            provider="pexels",
            url="https://www.pexels.com/video/holy-ganges-river-temple-varanasi-1234/",
            duration=10.0,
            width=1080,
            height=1920,
            source_info={
                "search_term": "India water",
                "title": "Holy Ganges river in Varanasi with ancient temple",
                "tags": ["ganges", "varanasi", "temple", "india", "river"],
            },
        )
        bad_score = score_candidate(bad_candidate, intent, requested_aspect=VideoAspect.portrait)
        self.assertFalse(bad_score.is_accepted)
        self.assertEqual(bad_score.negative_penalty, -50.0)
        self.assertIn("forbidden negative keyword", bad_score.rejection_reason)

        # Authentic Kerala candidate
        good_candidate = MaterialInfo(
            provider="pexels",
            url="https://www.pexels.com/video/kerala-alappuzha-backwaters-houseboat-5678/",
            duration=12.0,
            width=1080,
            height=1920,
            source_info={
                "search_term": "Kerala backwaters",
                "title": "Traditional wooden houseboat cruising on calm Kerala backwaters in Alappuzha",
                "tags": ["kerala", "alappuzha", "houseboat", "backwaters", "palm trees", "canal"],
            },
        )
        good_score = score_candidate(good_candidate, intent, requested_aspect=VideoAspect.portrait)
        self.assertTrue(good_score.is_accepted)
        self.assertGreaterEqual(good_score.total_score, 80.0)
        self.assertEqual(good_score.negative_penalty, 0.0)

    def test_goa_beach_vs_temple(self):
        intent = VisualIntent(
            subject="Goa sunny sandy beach on Arabian Sea",
            location="Goa, India",
            objects=["sandy beach", "ocean waves", "palm trees"],
            action="waves rolling on sunlit beach",
            stock_queries=["Goa beach Arabian sea", "Goa sunset beach"],
            negative_prompt=["temple", "mountains", "snow", "desert"],
            factual_visual=True,
        )

        # Temple candidate
        temple_candidate = MaterialInfo(
            provider="pixabay",
            url="https://pixabay.com/videos/ancient-hindu-temple-in-india-1111/",
            duration=8.0,
            width=1080,
            height=1920,
            source_info={
                "search_term": "India heritage",
                "title": "Ancient Hindu temple with stone carvings in South India",
                "tags": ["temple", "hindu", "carvings", "architecture"],
            },
        )
        temple_score = score_candidate(temple_candidate, intent, requested_aspect=VideoAspect.portrait)
        self.assertFalse(temple_score.is_accepted)
        self.assertEqual(temple_score.negative_penalty, -50.0)

        # Authentic Goa beach candidate
        beach_candidate = MaterialInfo(
            provider="pixabay",
            url="https://pixabay.com/videos/goa-beach-sunset-arabian-sea-2222/",
            duration=9.0,
            width=1080,
            height=1920,
            source_info={
                "search_term": "Goa beach",
                "title": "Goa sandy beach at sunset with waves from Arabian Sea",
                "tags": ["goa", "beach", "sunset", "arabian sea", "waves", "palm trees"],
            },
        )
        beach_score = score_candidate(beach_candidate, intent, requested_aspect=VideoAspect.portrait)
        self.assertTrue(beach_score.is_accepted)
        self.assertGreaterEqual(beach_score.total_score, 80.0)

    def test_taj_mahal_vs_generic_monument(self):
        intent = VisualIntent(
            subject="Taj Mahal white marble dome architecture",
            location="Agra, Uttar Pradesh, India",
            objects=["white marble dome", "minarets", "reflecting pool"],
            action="camera push-in to Taj Mahal facade",
            stock_queries=["Taj Mahal Agra sunrise", "Taj Mahal architecture"],
            negative_prompt=["modern skyscrapers", "beach", "traffic"],
            factual_visual=True,
        )

        # Generic unrelated monument candidate
        monument_candidate = MaterialInfo(
            provider="pexels",
            url="https://www.pexels.com/video/historical-qutub-minar-monument-3333/",
            duration=6.0,
            width=1080,
            height=1920,
            source_info={
                "search_term": "India monument",
                "title": "Historical stone monument tower Qutub Minar in Delhi",
                "tags": ["monument", "delhi", "tower", "stone", "history"],
            },
        )
        monument_score = score_candidate(monument_candidate, intent, requested_aspect=VideoAspect.portrait)
        self.assertFalse(monument_score.is_accepted)
        self.assertLess(monument_score.total_score, 80.0)

        # Authentic Taj Mahal candidate
        taj_candidate = MaterialInfo(
            provider="pexels",
            url="https://www.pexels.com/video/taj-mahal-agra-white-marble-sunrise-4444/",
            duration=10.0,
            width=1080,
            height=1920,
            source_info={
                "search_term": "Taj Mahal",
                "title": "Pristine white marble Taj Mahal in Agra with reflecting pool",
                "tags": ["taj mahal", "agra", "marble", "dome", "minarets", "pool", "sunrise"],
            },
        )
        taj_score = score_candidate(taj_candidate, intent, requested_aspect=VideoAspect.portrait)
        self.assertTrue(taj_score.is_accepted)
        self.assertGreaterEqual(taj_score.total_score, 80.0)

    def test_generic_office_scene(self):
        intent = VisualIntent(
            subject="Modern business office team productivity",
            location="",
            objects=["laptop", "glass boardroom", "charts"],
            action="coworkers collaborating on laptops",
            stock_queries=["modern business office teamwork", "corporate productivity"],
            negative_prompt=["vintage computers", "cluttered room"],
            factual_visual=False,
        )

        office_candidate = MaterialInfo(
            provider="pexels",
            url="https://www.pexels.com/video/diverse-team-working-in-modern-office-5555/",
            duration=8.0,
            width=1080,
            height=1920,
            source_info={
                "search_term": "office teamwork",
                "title": "Diverse corporate team collaborating on laptops in modern glass office",
                "tags": ["office", "team", "business", "modern", "laptop", "productivity"],
            },
        )
        office_score = score_candidate(
            office_candidate, intent, requested_aspect=VideoAspect.portrait, generic_threshold=65.0
        )
        self.assertTrue(office_score.is_accepted)
        self.assertGreaterEqual(office_score.total_score, 65.0)

    def test_low_relevance_scores_rejected(self):
        intent = VisualIntent(
            subject="High-speed server neural network data flow",
            location="",
            objects=["server racks", "fiber optic cables"],
            action="glowing data pulses streaming",
            stock_queries=["server datacenter neural network"],
            negative_prompt=["blurry", "static"],
            factual_visual=False,
        )

        # Barely relevant candidate (e.g. coffee mug on desk)
        unrelated_candidate = MaterialInfo(
            provider="pexels",
            url="https://www.pexels.com/video/morning-coffee-cup-6666/",
            duration=7.0,
            width=1080,
            height=1920,
            source_info={
                "search_term": "desk",
                "title": "Steaming cup of coffee on wooden table",
                "tags": ["coffee", "morning", "table", "cup"],
            },
        )
        score = score_candidate(unrelated_candidate, intent, requested_aspect=VideoAspect.portrait)
        self.assertFalse(score.is_accepted)
        self.assertLess(score.total_score, 65.0)


class TestStockRetriever(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_retrieve_stock_no_search_results(self):
        scene = ScenePlan(
            scene_id="scene_001",
            scene_index=1,
            narration="Exploring unknown territories.",
            duration_seconds=5.0,
            visual_intent=VisualIntent(
                subject="Rare deep sea creature",
                stock_queries=["deep sea abyssal bioluminescence creature"],
                factual_visual=False,
            ),
        )

        with patch("app.services.material._search_videos_with_cache", return_value=[]):
            result = retrieve_stock_for_scene(scene, source="pexels")
            self.assertIsNone(result)

    def test_retrieve_stock_success_and_saves_to_material_directory(self):
        scene = ScenePlan(
            scene_id="scene_002",
            scene_index=1,
            narration="Visiting the magnificent Taj Mahal.",
            duration_seconds=6.0,
            visual_intent=VisualIntent(
                subject="Taj Mahal Agra marble facade",
                location="Agra, India",
                objects=["marble dome", "minarets"],
                stock_queries=["Taj Mahal Agra sunrise"],
                factual_visual=True,
            ),
        )

        good_candidate = MaterialInfo(
            provider="pexels",
            url="https://www.pexels.com/video/taj-mahal-sample-video-7777/",
            duration=8.0,
            width=1080,
            height=1920,
            source_info={
                "search_term": "Taj Mahal",
                "title": "Taj Mahal in Agra with white marble dome",
                "tags": ["taj mahal", "agra", "marble", "dome"],
            },
        )

        saved_file_path = os.path.join(self.temp_dir, "vid-taj-sample.mp4")
        with open(saved_file_path, "wb") as f:
            f.write(b"fake mp4 video bytes")

        with (
            patch("app.services.material._search_videos_with_cache", return_value=[good_candidate]),
            patch("app.services.material.save_video", return_value=saved_file_path),
        ):
            scored_result = retrieve_stock_for_scene(
                scene=scene,
                source="pexels",
                video_aspect=VideoAspect.portrait,
                material_directory=self.temp_dir,
            )

            self.assertIsNotNone(scored_result)
            self.assertEqual(scored_result.scene_id, "scene_002")
            self.assertEqual(scored_result.local_path, saved_file_path)
            self.assertTrue(scored_result.score.is_accepted)
            self.assertGreaterEqual(scored_result.score.total_score, 80.0)


if __name__ == "__main__":
    unittest.main()
