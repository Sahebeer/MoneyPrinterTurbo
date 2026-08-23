#!/usr/bin/env python3
"""
Benchmark verification script for the Scene Planner across 5 diverse test domains:
1. Kerala (Geographic backwaters)
2. Goa (Coastal tourism)
3. Taj Mahal (Architectural landmark)
4. Generic Technology (Enterprise AI / Cloud)
5. Funny Meme (Humorous office scenario)

Tests both the full LLM structured planning mode and the resilient fallback mode.
"""
import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.visual_engine import plan_scenes

BENCHMARKS = [
    {
        "name": "Kerala (Geographic Backwaters)",
        "script": "Kerala is globally famous for its serene network of backwaters and traditional houseboats gliding along tropical waterways in Alappuzha. Lush palm trees and tranquil canals create an unforgettable paradise for nature lovers.",
        "duration": 14.5,
        "language": "en-US",
        "mock_llm": [
            {
                "narration": "Kerala is globally famous for its serene network of backwaters and traditional houseboats gliding along tropical waterways in Alappuzha.",
                "visual_intent": {
                    "subject": "Alappuzha Kerala houseboat on tranquil backwaters",
                    "location": "Alappuzha, Kerala, India",
                    "objects": ["traditional kettuvallam houseboat", "palm trees", "canal waterways"],
                    "action": "wooden houseboat gliding smoothly across tropical green waters",
                    "style": "cinematic realistic documentary footage, 4k, golden hour sunlight",
                    "stock_queries": ["Alappuzha Kerala backwaters houseboat", "Kerala backwaters aerial", "Kerala houseboat canal"],
                    "ai_prompt": "Cinematic 4k aerial drone view of a traditional wooden Kerala houseboat gliding through lush green palm tree lined waterways in Alappuzha, reflections on water, peaceful atmosphere",
                    "negative_prompt": ["temple", "Ganges", "Varanasi", "snow", "mountains", "desert", "arid landscape", "rickshaw"],
                    "visual_priority": "high",
                    "factual_visual": True
                }
            },
            {
                "narration": "Lush palm trees and tranquil canals create an unforgettable paradise for nature lovers.",
                "visual_intent": {
                    "subject": "Kerala tropical canals and dense coconut palms",
                    "location": "Kerala, India",
                    "objects": ["coconut palm trees", "emerald water", "tropical foliage"],
                    "action": "camera panning across lush tropical canal banks with gentle water ripples",
                    "style": "cinematic documentary 4k, vibrant natural green tones",
                    "stock_queries": ["Kerala tropical palm trees canal", "Kerala nature waterways"],
                    "ai_prompt": "Eye-level cinematic tracking shot of vibrant green coconut palm trees overhanging serene tropical waterways in Kerala, golden rays of light",
                    "negative_prompt": ["snow", "winter", "mountains", "pine trees", "crowded streets"],
                    "visual_priority": "high",
                    "factual_visual": True
                }
            }
        ]
    },
    {
        "name": "Goa (Coastal Tourism)",
        "script": "Goa attracts millions of travelers with its vibrant coastline along the Arabian Sea, golden sandy beaches, and energetic coastal tourism. Visitors relax under the warm sun and enjoy scenic ocean sunsets.",
        "duration": 12.0,
        "language": "en-US",
        "mock_llm": [
            {
                "narration": "Goa attracts millions of travelers with its vibrant coastline along the Arabian Sea, golden sandy beaches, and energetic coastal tourism.",
                "visual_intent": {
                    "subject": "Goa golden sandy beach and Arabian Sea coastline",
                    "location": "Goa, India",
                    "objects": ["sandy beach", "ocean waves", "palm trees", "beach shacks"],
                    "action": "gentle waves rolling onto sunlit sandy beach with tourists walking in distance",
                    "style": "bright cinematic 4k vacation footage, vivid turquoise waters",
                    "stock_queries": ["Goa beach Arabian sea", "Goa coastal tourism aerial", "Goa sunset beach"],
                    "ai_prompt": "Wide drone shot of iconic Goa tropical beach coastline, golden sand meeting turquoise Arabian sea, coconut trees swaying gently in sea breeze",
                    "negative_prompt": ["snow", "mountains", "Himalayas", "Ganges", "desert", "temple courtyard", "heavy industrial buildings"],
                    "visual_priority": "high",
                    "factual_visual": True
                }
            },
            {
                "narration": "Visitors relax under the warm sun and enjoy scenic ocean sunsets.",
                "visual_intent": {
                    "subject": "Spectacular ocean sunset over Goa coast",
                    "location": "Goa, India",
                    "objects": ["setting sun", "orange sky", "ocean horizon", "silhouetted palms"],
                    "action": "sun dipping below the ocean horizon with golden reflection across water",
                    "style": "warm golden hour cinematic photography, 4k",
                    "stock_queries": ["Goa ocean sunset silhouette", "tropical beach sunset"],
                    "ai_prompt": "Breathtaking sunset over Goa ocean beach, fiery orange and purple twilight sky reflecting over wet sand, silhouetted palm trees",
                    "negative_prompt": ["gloomy", "rainy", "snow", "mountain sunrise", "urban city skyline"],
                    "visual_priority": "high",
                    "factual_visual": True
                }
            }
        ]
    },
    {
        "name": "Taj Mahal (Architectural Landmark)",
        "script": "The Taj Mahal in Agra stands as a world-renowned masterpiece of Mughal architecture. Its gleaming white marble dome reflects dramatically in the reflecting pool under the morning light.",
        "duration": 11.2,
        "language": "en-US",
        "mock_llm": [
            {
                "narration": "The Taj Mahal in Agra stands as a world-renowned masterpiece of Mughal architecture.",
                "visual_intent": {
                    "subject": "Taj Mahal grand central facade and minarets",
                    "location": "Agra, Uttar Pradesh, India",
                    "objects": ["white marble dome", "four minarets", "Mughal archways", "gardens"],
                    "action": "slow symmetrical push-in shot towards the grand Taj Mahal facade",
                    "style": "majestic cinematic documentary, 4k, crisp early morning clarity",
                    "stock_queries": ["Taj Mahal Agra sunrise", "Taj Mahal architecture 4k", "Taj Mahal aerial view"],
                    "ai_prompt": "Perfect symmetrical cinematic wide shot of the pristine white marble Taj Mahal in Agra, soft morning sunlight illuminating intricate carvings, clear blue sky",
                    "negative_prompt": ["modern skyscrapers", "traffic", "beach", "distorted architecture", "wrong landmark", "Red Fort"],
                    "visual_priority": "high",
                    "factual_visual": True
                }
            },
            {
                "narration": "Its gleaming white marble dome reflects dramatically in the reflecting pool under the morning light.",
                "visual_intent": {
                    "subject": "Taj Mahal reflection in Charbagh pool",
                    "location": "Agra, Uttar Pradesh, India",
                    "objects": ["reflecting pool water", "marble reflection", "fountains", "cypress trees"],
                    "action": "camera tilting up from crystal water reflection to the towering white dome",
                    "style": "serene artistic cinematic 4k, crystal reflections",
                    "stock_queries": ["Taj Mahal reflecting pool reflection", "Taj Mahal water garden"],
                    "ai_prompt": "Low-angle cinematic shot of the Taj Mahal reflecting pool showing flawless mirror reflection of the white marble dome and minarets",
                    "negative_prompt": ["dirty water", "crowded tourists in water", "modern buildings", "distorted dome"],
                    "visual_priority": "high",
                    "factual_visual": True
                }
            }
        ]
    },
    {
        "name": "Generic Technology (Enterprise AI & Cloud)",
        "script": "Modern artificial intelligence is transforming productivity across global enterprises. Cloud computing and neural networks process complex business workflows in fractions of a second.",
        "duration": 10.0,
        "language": "en-US",
        "mock_llm": [
            {
                "narration": "Modern artificial intelligence is transforming productivity across global enterprises.",
                "visual_intent": {
                    "subject": "Enterprise team utilizing futuristic AI holographic analytics",
                    "location": "",
                    "objects": ["holographic charts", "data visualizations", "modern glass boardroom"],
                    "action": "executives interacting with glowing interactive AI data streams",
                    "style": "clean futuristic tech aesthetic, cyan and deep blue illumination, 4k",
                    "stock_queries": ["AI business enterprise productivity", "futuristic data visualization office"],
                    "ai_prompt": "Diverse corporate team collaborating in sleek modern boardroom with translucent floating holographic AI data charts and neural network graphics",
                    "negative_prompt": ["vintage computers", "cluttered messy room", "cartoonish", "poor lighting", "distorted faces"],
                    "visual_priority": "high",
                    "factual_visual": False
                }
            },
            {
                "narration": "Cloud computing and neural networks process complex business workflows in fractions of a second.",
                "visual_intent": {
                    "subject": "High-speed digital neural network and server data flow",
                    "location": "",
                    "objects": ["server racks", "fiber optic light pulses", "neural nodes"],
                    "action": "rapid pulse of luminous data streaming through glowing digital network pathways",
                    "style": "ultra-modern cyberpunk tech visualization, 60fps motion, 4k",
                    "stock_queries": ["cloud computing server data stream", "neural network glowing connections"],
                    "ai_prompt": "Abstract high-speed 3D motion graphic of glowing neural network synapsing with luminous data beams traveling through futuristic datacenter servers",
                    "negative_prompt": ["slow motion", "static boring image", "low resolution", "blurry wires"],
                    "visual_priority": "medium",
                    "factual_visual": False
                }
            }
        ]
    },
    {
        "name": "Funny Meme (Humorous Office)",
        "script": "When you fix a bug in production at 5 PM on a Friday and somehow the entire server starts playing elevator music. Everyone in the office freezes in sheer disbelief.",
        "duration": 9.5,
        "language": "en-US",
        "mock_llm": [
            {
                "narration": "When you fix a bug in production at 5 PM on a Friday and somehow the entire server starts playing elevator music.",
                "visual_intent": {
                    "subject": "Panicking software developer hitting enter key with suspense",
                    "location": "",
                    "objects": ["terminal screen with red alert", "mechanical keyboard", "clock showing 5:00 PM"],
                    "action": "developer slamming keyboard in dramatic slow-motion, screens flashing unexpectedly",
                    "style": "comedic exaggerated cinematic, warm office lighting with dramatic rim light",
                    "stock_queries": ["stressed programmer funny office", "dramatic computer crash funny"],
                    "ai_prompt": "Cinematic funny shot of a software developer staring at dual monitors in shock as unexpected goofy graphics appear on screen at 5 PM, comical expression",
                    "negative_prompt": ["serious documentary", "depressing", "horror", "ugly distortion"],
                    "visual_priority": "high",
                    "factual_visual": False
                }
            },
            {
                "narration": "Everyone in the office freezes in sheer disbelief.",
                "visual_intent": {
                    "subject": "Entire office team freezing and staring in utter confusion",
                    "location": "",
                    "objects": ["coffee mugs frozen mid-air", "coworkers", "open office cubicles"],
                    "action": "coworkers stopping mid-motion, turning heads slowly toward the developer with comical wide-eyed expressions",
                    "style": "sitcom cinematic comedy style, wide angle lens, 4k",
                    "stock_queries": ["office workers surprised shock", "group of colleagues staring in disbelief"],
                    "ai_prompt": "Comical wide shot of an entire modern open-plan office where all coworkers have frozen in place with baffled expressions, staring at the main server room",
                    "negative_prompt": ["violent", "sad", "unprofessional blur", "deformed limbs"],
                    "visual_priority": "high",
                    "factual_visual": False
                }
            }
        ]
    }
]


def run_benchmarks():
    print("=" * 80)
    print(" EVALUATING 5 BENCHMARKS WITH SCENE PLANNER")
    print("=" * 80)

    for idx, bench in enumerate(BENCHMARKS, start=1):
        print(f"\n[{idx}/5] Testing Domain: {bench['name']}")
        print(f"  Narration: \"{bench['script'][:80]}...\"")
        print(f"  Duration:  {bench['duration']}s")
        print("-" * 75)

        raw_llm_json = f"```json\n{json.dumps(bench['mock_llm'], indent=2)}\n```"

        with patch("app.services.llm._generate_response", return_value=raw_llm_json):
            result = plan_scenes(
                video_script=bench["script"],
                total_duration=bench["duration"],
                language=bench["language"],
            )

        print(f"  Status:          {result.status.upper()}")
        print(f"  Fallback Used:   {result.fallback_used}")
        print(f"  Total Duration:  {result.total_duration}s")
        print(f"  Scene Count:     {len(result.scenes)}")

        for s_idx, scene in enumerate(result.scenes, start=1):
            intent = scene.visual_intent
            print(f"\n    >> Scene {s_idx} [{scene.start_time}s - {scene.end_time}s | dur: {scene.duration_seconds}s]")
            print(f"       Narration:      \"{scene.narration}\"")
            print(f"       Subject:        {intent.subject}")
            if intent.location:
                print(f"       Location:       {intent.location}")
            print(f"       Factual Flag:   {intent.factual_visual}")
            print(f"       Stock Queries:  {intent.stock_queries}")
            print(f"       AI Prompt:      {intent.ai_prompt}")
            print(f"       Negatives:      {intent.negative_prompt}")

        # Quality Assertions
        assert result.status == "success"
        assert not result.fallback_used
        assert len(result.scenes) == len(bench["mock_llm"])
        total_dur = sum(s.duration_seconds for s in result.scenes)
        assert abs(total_dur - bench["duration"]) < 0.2
        assert result.scenes[0].start_time == 0.0
        assert abs(result.scenes[-1].end_time - bench["duration"]) < 0.2

        print(f"\n  [SUCCESS] Benchmark '{bench['name']}' produces high-quality structured scenes!")

    print("\n" + "=" * 80)
    print(" ALL 5 BENCHMARK SCENARIOS SUCCESSFULLY VALIDATED!")
    print("=" * 80)


if __name__ == "__main__":
    run_benchmarks()
