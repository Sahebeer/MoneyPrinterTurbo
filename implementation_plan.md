The implementation plan
Phase 0 — Freeze the existing application
Do not modify the current video generation behavior initially.
Before anything:
Current MoneyPrinterTurbo
        │
        ├── Pexels
        ├── Pixabay
        ├── existing script generation
        ├── existing TTS
        └── existing video composition
We add:
              NEW
               │
               ▼
       Semantic Visual Engine
               │
        ┌──────┼──────┐
        ▼      ▼      ▼
      Pexels Pixabay  AI
This means if our new system breaks, we can simply switch back to:
video_source = "pexels"
or whatever your current configuration uses.
Do not delete the existing implementation.

⸻

Phase 1 — First inspect MoneyPrinterTurbo
Before Antigravity changes anything, have it understand the repository.
Do NOT ask Antigravity to implement yet.
Give it this first:
You are working on the existing MoneyPrinterTurbo repository.
DO NOT modify, delete, rename, refactor, or create files yet.
Your only task is to perform a complete read-only architecture audit of the repository.
I am planning to add a new semantic visual generation system that will:
1. Analyze generated narration/script into visual scenes.
2. Search Pexels and Pixabay using highly specific semantic queries.
3. Use AI-generated video when stock footage is not sufficiently relevant.
4. Prefer image-to-video for factual/location-specific visuals where visual correctness matters.
5. Use text-to-video for conceptual or generic scenes.
6. Preserve the existing MoneyPrinterTurbo video generation pipeline.
7. Allow the new visual engine to be enabled/disabled through configuration.
8. Eventually support Hugging Face Inference Providers / Wan2.2 TI2V-5B.
9. Save generated assets into the existing material_directory/material storage mechanism.
10. Produce a final video whose visual scenes are aligned with the narration timing.
Audit the repository and report:
A. Project structure
* Main entry points
* CLI/UI entry points
* configuration files
* environment files
* video generation modules
* script generation modules
* TTS modules
* subtitle/caption modules
* video composition modules
* material_directory handling
* temporary file handling
* Pexels integration
* Pixabay integration
* existing video_source logic
* existing local-video support
B. Exact execution flowTrace one complete video generation from:topic/input→ script→ scene/paragraph generation→ narration/TTS→ visual material acquisition→ video composition→ final output.
C. Identify the exact files and functions where:
* script is created
* script is segmented
* narration duration is known
* Pexels is searched
* Pixabay is searched
* downloaded assets are stored
* local video assets are consumed
* video clips are trimmed/looped
* final video is composed
D. Identify existing abstractions we can reuse.
E. Identify the minimum number of files that need to be added/modified for the new semantic visual engine.
F. Identify potential compatibility risks.
G. Identify anything that must NOT be changed.
H. Produce a proposed implementation architecture, but do not implement it.
IMPORTANT:
* Do not invent files or functions.
* Reference actual paths and function/class names found in the repository.
* Do not make code changes.
* Do not install dependencies.
* Do not modify configuration.
* Do not delete anything.
Return only the audit and proposed architecture.
Why this matters
This prevents Antigravity from hallucinating your repo structure.
Send this first.
Then inspect its response yourself.

⸻

Phase 2 — Create the architecture document
Once the audit is correct, create something like:
docs/
    semantic_visual_engine.md
This becomes the source of truth for the implementation.
Don’t let Antigravity keep the entire architecture in its context.
The document should define:
Semantic Visual Engine
│
├── Scene Planner
├── Visual Intent
├── Stock Search
├── Relevance Scoring
├── AI Video Provider
├── AI Image Provider
├── Asset Cache
├── Fallback Manager
└── Existing Composer Adapter

⸻

Phase 3 — Define the scene schema
This is arguably the most important part.
We need to stop thinking:
paragraph → video
and move to:
narration → visual scenes
Each scene should contain something conceptually like:
{
  "scene_id": "scene_003",
  "narration": "Kerala is famous for its extensive network of backwaters.",
  "duration_seconds": 6.8,

  "visual_intent": {
    "subject": "Kerala backwaters",
    "location": "Alappuzha, Kerala, India",
    "objects": [
      "traditional Kerala houseboat",
      "tropical waterways"
    ],
    "action": "houseboat moving slowly through backwaters",
    "style": "realistic documentary footage",

    "stock_queries": [
      "Alappuzha Kerala backwaters houseboat",
      "Kerala backwater houseboat",
      "Kerala backwaters aerial"
    ],

    "ai_prompt": "Cinematic realistic aerial documentary footage of Kerala backwaters near Alappuzha...",
    
    "negative_prompt": [
      "Ganges",
      "Varanasi",
      "temple",
      "snow",
      "mountains",
      "generic Indian river"
    ],

    "visual_priority": "high",
    "factual_visual": true
  }
}
This is how we prevent the Goa → random temple problem.

⸻

Phase 4 — Build the Scene Planner
The Scene Planner takes the existing generated script and asks an LLM:
What visual should be shown at every point in this narration?
It should NOT generate videos.
It only produces structured scene data.
Example
Narration:
“Goa is famous for its long sandy beaches and vibrant coastal tourism.”
Planner:
Scene 1
0–6 sec
Goa beach
Arabian Sea
tourists
sand
waves

Scene 2
6–12 sec
Goa coastal tourism
beach activities
sunset
Not:
"India beach"

⸻

Phase 5 — Duration calculation
This needs to connect to your existing TTS pipeline.
We shouldn’t guess:
duration = len(text) / 10
if the actual narration audio already exists.
Instead:
Generate narration
       ↓
Get actual audio duration
       ↓
Split narration into scenes
       ↓
Assign duration to scenes
For example:
Audio = 57.4 seconds

Scene 1 = 6.2
Scene 2 = 7.8
Scene 3 = 5.6
Scene 4 = 8.1
...
The visual engine receives actual timing.

⸻

Phase 6 — Build the stock retrieval engine
Now we improve Pexels/Pixabay.
Instead of:
search("Kerala")
we do:
search(
    "Alappuzha Kerala backwaters houseboat"
)
and potentially multiple queries.
Query hierarchy
Exact
↓
Specific
↓
Related
↓
Generic
Example:
1. "Alappuzha Kerala backwaters houseboat"
2. "Kerala backwater houseboat"
3. "Kerala tropical waterways"
4. "Indian tropical backwaters"
But we should not automatically accept #4.
That leads directly to your current problem.

⸻

Phase 7 — Add visual relevance scoring
This is the second major improvement.
Every returned stock clip gets a score.
Something conceptually like:
Relevance Score
────────────────
Location match       30
Subject match        30
Object match         15
Action match         10
Semantic similarity  10
Orientation           5
────────────────────
Total                100
Then:
>= 80 → excellent
65–79 → acceptable
50–64 → weak
< 50  → reject
For important factual scenes:
minimum_score = 80
For generic scenes:
minimum_score = 60
This is much safer.

⸻

Phase 8 — AI generation becomes the fallback
Only after stock fails:
Stock search
     ↓
Score
     ↓
Score >= threshold?
     │
   YES ─────→ use stock
     │
    NO
     ↓
AI generation
This saves enormous amounts of generation.

⸻

Phase 9 — AI generation provider abstraction
Create something conceptually like:
class VideoProvider:
    def generate_text_to_video(...)
    def generate_image_to_video(...)
Then:
VideoProvider
│
├── HuggingFaceProvider
│
├── LocalWanProvider       # future
│
└── OtherProvider          # future
Do not hardcode Fal directly into the whole application.
Hugging Face currently exposes the provider abstraction and documents Wan2.2 TI2V-5B through provider routing.  

⸻

Phase 10 — Use TI2V-5B strategically
This is the model I’d test first.
Wan’s official repository lists:
* T2V
* I2V
* TI2V
* 480p
* 720p
and specifically describes TI2V-5B as the combined text/image-to-video model.  
So:
Factual visual
Image
 ↓
TI2V
 ↓
animated video
Conceptual visual
Prompt
 ↓
TI2V
 ↓
video

⸻

Phase 11 — Image → Video should be preferred for factual locations
For:
* Taj Mahal
* Gateway of India
* Goa beach
* Kerala backwaters
* Eiffel Tower
* specific cars
* specific products
* historical buildings
we should prefer:
Correct image
     ↓
I2V
rather than:
Text
 ↓
AI video
Why?
Because text-to-video models can hallucinate geographic details.
The image provides the visual anchor.

⸻

Phase 12 — Where do we get the anchor image?
I’d build this in stages.
V1
Use Pexels/Pixabay image search.
specific query
↓
best image
↓
AI I2V
V2
Add a dedicated image-generation provider.
But don’t add this now.
It creates another dependency and another failure mode.
We first prove:
Pexels/Pixabay image → Wan I2V

⸻

Phase 13 — AI prompt engineering
The planner should generate:
Positive prompt
Realistic cinematic documentary footage of
[exact subject]
in
[exact location].

The scene should clearly show:
[list]

Natural lighting,
realistic geography,
real-world proportions,
documentary photography,
slow camera movement.
Negative prompt
This is extremely important.
For Kerala:
Ganges,
Varanasi,
North Indian architecture,
desert,
Himalayas,
snow,
temples,
generic India,
incorrect geography
For Goa:
temple,
mountains,
snow,
desert,
Ganges,
North Indian architecture,
inland city,
incorrect coastline
The scene planner generates these dynamically.
Hugging Face’s current text-to-video API specification explicitly supports a negative_prompt parameter, along with frame count, guidance scale, inference steps and seed.  

⸻

Phase 14 — Add deterministic seeds
Every generated scene should store:
{
    "seed": 18273645
}
Why?
If generation fails or you want to reproduce it, we can regenerate the same scene.

⸻

Phase 15 — Build an asset cache
This is extremely important for GitHub Actions.
Never regenerate something unnecessarily.
Structure:
material_directory/
    semantic_visuals/
        <project_id>/
            scene_001/
                metadata.json
                source.jpg
                video.mp4
            scene_002/
                metadata.json
                video.mp4
Metadata:
{
  "scene_id": "scene_002",
  "prompt": "...",
  "provider": "huggingface",
  "model": "Wan-AI/Wan2.2-TI2V-5B",
  "seed": 12345,
  "duration": 6,
  "created_at": "...",
  "source": "ai",
  "status": "success"
}
If the GitHub Action fails halfway:
Scene 1 ✓
Scene 2 ✓
Scene 3 ✓
Scene 4 ✗
Next run should not regenerate scenes 1–3.
It resumes at scene 4.
That’s a major optimization.

⸻

Phase 16 — Add retries, but intelligently
Never:
while not success:
    generate()
Use:
Attempt 1
   ↓
failure
   ↓
wait
   ↓
Attempt 2
   ↓
failure
   ↓
fallback to stock
Maximum:
2 AI attempts / scene
Then fallback.

⸻

Phase 17 — Handle provider failures
Example:
HF unavailable
       ↓
Try stock
       ↓
If stock exists → continue
       ↓
If no stock → mark scene degraded
The entire video should not fail because Scene 7 failed.

⸻

Phase 18 — Add quality states
Every scene should end up as:
EXCELLENT
GOOD
ACCEPTABLE
FALLBACK
FAILED
And the final project can report:
Visual quality
───────────────
Excellent      7
Good           3
Fallback       1
Failed         0

⸻

Phase 19 — Composition adapter
Don’t rewrite your editor.
Convert our scene assets into the format the current MoneyPrinterTurbo composer already expects.
Conceptually:
SemanticScene
     ↓
Existing VideoClip representation
     ↓
Existing compositor
This is critical.
The semantic engine should know nothing about subtitles, transitions, music, etc.
Its only job:
Give the existing editor the right visual clips.

⸻

Phase 20 — Configuration
Add a new configuration section.
Something conceptually like:
[visual_engine]

enabled = false
mode = "hybrid"

stock_enabled = true
ai_enabled = true

stock_min_score = 65
factual_min_score = 80

prefer_i2v_for_factual = true

max_ai_attempts = 2

cache_enabled = true

provider = "huggingface"
model = "Wan-AI/Wan2.2-TI2V-5B"
Initially:
enabled = false
So nothing breaks.
After testing:
enabled = true

⸻

Phase 21 — Environment variables
Never put tokens in TOML or source code.
For example:
HF_TOKEN=...
PEXELS_API_KEY=...
PIXABAY_API_KEY=...
Your GitHub Actions secrets should contain the same credentials.

⸻

Phase 22 — Local development mode
We should create:
VISUAL_ENGINE_MODE=mock
The mock provider creates placeholder assets.
That means you can test:
script
→ scene planner
→ scene timing
→ asset selection
→ composition
without burning AI generations.
This is very important.

⸻

Phase 23 — Test with your exact problematic examples
Don’t test with random prompts.
Use:
Test A
“Kerala is famous for its backwaters…”
Expected:
Kerala backwaters
Alappuzha
houseboat
Never:
Ganges
Varanasi
temple
Test B
“Goa’s beaches attract millions of visitors…”
Expected:
Goa coastline
Arabian Sea
sandy beach
Not:
random Indian temple
Test C
“The Taj Mahal attracts visitors from around the world…”
Expected:
Taj Mahal
Agra
Test D
“India’s IT industry employs millions…”
Generic stock is perfectly acceptable.
We don’t need AI for every sentence.

⸻

Phase 24 — Automated semantic validation
This is the extra layer I’d add.
After obtaining a visual, we can use an image/video frame + vision model to ask:
Does this visual actually represent the intended scene?
Example:
Expected:
Kerala backwaters + houseboat

Actual:
River + temple

Result:
FAIL
Then:
stock → vision validation → reject
                         ↓
                     AI generate
This is much stronger than keyword matching.
We don’t need to run expensive validation on every generic scene.
Only:
factual_visual == true

⸻

Phase 25 — The final decision engine
Ultimately:
                 Scene
                   │
                   ▼
           Is visual factual?
             /            \
           YES             NO
            │               │
            ▼               ▼
     Search specific     Search stock
         stock                │
            │                 │
            ▼                 ▼
       Score result       Score result
            │                 │
       >= 80?             >= 65?
        /   \              /   \
      YES    NO           YES    NO
       │      │            │      │
       ▼      ▼            ▼      ▼
     STOCK   AI I2V      STOCK   AI T2V
              │
              ▼
        Vision validation
              │
          ┌───┴───┐
         PASS    FAIL
          │        │
          ▼        ▼
        ACCEPT   retry/fallback
That’s the actual system I’d want.

⸻

Phase 26 — GitHub Actions
Your weekly workflow should become:
GitHub Action
     │
     ▼
Generate script
     │
     ▼
Generate narration
     │
     ▼
Scene planner
     │
     ▼
Check cache
     │
     ├── cached → reuse
     │
     └── missing
            │
            ▼
       Stock search
            │
            ▼
       relevance check
            │
      ┌─────┴─────┐
      ▼           ▼
    good         bad
      │           │
      ▼           ▼
    stock       AI
                  │
                  ▼
              save cache
                  │
                  ▼
               compose
                  │
                  ▼
             final video
This means the workflow doesn’t care whether a scene came from Pexels, Pixabay or Wan.

⸻

Phase 27 — Don’t make GitHub Actions generate huge numbers of AI clips
Set a safety budget.
For example:
MAX_AI_SCENES_PER_VIDEO = 10
If the planner produces 20 scenes:
10 AI max
remaining → stock/fallback
Later you can increase it.
This prevents accidental API abuse.

⸻

Phase 28 — First MVP target
Don’t attempt the entire system immediately.
The first milestone should be:
MVP-1
Existing script
      ↓
Scene planner
      ↓
3–5 scenes
      ↓
specific Pexels/Pixabay queries
      ↓
best asset
      ↓
existing composer
No AI.
Prove that semantic scene planning alone improves your current output.

⸻

MVP-2
Add:
Pexels/Pixabay
      ↓
no sufficiently relevant result
      ↓
Wan2.2 TI2V
      ↓
video

⸻

MVP-3
Add:
factual scene
      ↓
stock image
      ↓
Wan I2V

⸻

MVP-4
Add:
vision validation

⸻

MVP-5
Add:
cache
resume
retry
GitHub Actions
