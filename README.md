# Conceptly Studio 🎬🤖

**Enterprise Autonomous 9:16 Vertical Reel Generation Platform & Creator Studio**  
Designed for NCERT (Classes 6–10), IIT-JEE, NEET, and UPSC curricula, conforming strictly to [CONTRACT.md](CONTRACT.md) and syncing directly into Conceptly Core.

---

## ⚡ Key Highlights

* **Dual-Tier Generation Engine:**
  * **⚡ Default Mode (Fast & Free):** Powered by **Google Gemini 1.5 Flash** + **Microsoft Azure Neural TTS (`edge-tts`)** + Procedural Motion Cards. Renders in **10–15 seconds** at **~$0.0015 / reel**.
  * **💎 Premium Mode (Cinematic):** Powered by **Anthropic Claude 3.5 Sonnet / GPT-4o** + **ElevenLabs Neural Voice** + Enhanced Motion Visuals. Renders in **30–45 seconds** at **~$0.055 / reel**.
* **Strategic 3-Gate Human-in-the-Loop (HITL) Workflow:**
  * **Gate 1:** Creative Blueprint & 4-Act Screenplay Review (Word meter, hook paradox, visual directions).
  * **Gate 2:** Pedagogical Assessment Checkpoint (MCQs, distractors, and explanations).
  * **Gate 3:** Mobile Simulator Review (9:16 iPhone player mockup with **Safe Zone Overlay Switch** to verify top 120px & bottom 320px clearance) $\to$ One-click Live Publishing!
* **Blazing Fast Compositing:** Hardware-accelerated one-pass FFmpeg rendering with kinetic subtitles and audio ducking (`-14 LUFS` speech / `-22 dB` lofi ambient BGM).

---

## 🚀 Quick Start

### 1. Prerequisites
* Python 3.9+
* FFmpeg (`brew install ffmpeg` on macOS, or `apt install ffmpeg` on Linux)

### 2. Setup Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Variables
Copy `.env.example` to `.env` and optionally configure API keys:
```bash
cp .env.example .env
```
*(Note: If no external LLM keys are supplied, Studio automatically runs on its built-in offline pedagogical engine for local testing!)*

---

## 🖥️ Launch the Studio Web UI

Start the unified FastAPI server:
```bash
./venv/bin/python -m src.main
```
Open your browser and navigate to:
👉 **[http://localhost:8000/](http://localhost:8000/)** (or `http://localhost:8000/studio`)

* **Default Admin Credentials:** `admin@conceptly.app` / `admin123456`
* **Features in UI:**
  * Toggle between **⚡ Default Mode** and **💎 Premium Mode**.
  * Launch generation runs across NCERT, JEE, NEET, and UPSC syllabi.
  * Live status tracking across all 11 pipeline stages.
  * Interactive Gate 1, Gate 2, and Gate 3 review modals with the mobile safe-zone simulator.

---

## 💻 CLI Generation (Terminal Mode)

You can also run autonomous generation directly from your terminal:
```bash
./venv/bin/python -m src.cli --topic "Newton's Third Law" --class-level 9 --subject "Physics" --tier DEFAULT
```
To automatically publish to Conceptly Core:
```bash
./venv/bin/python -m src.cli --topic "Photosynthesis" --class-level 10 --subject "Biology" --tier PREMIUM --publish
```

---

## 🐳 Docker Deployment

Run the complete platform in a single container with pre-bundled FFmpeg and system typography:
```bash
docker compose up -d
```
The Studio Web UI and REST API will be live on port `8000`.

---

## 📐 Video & Media Specifications (CONTRACT.md Compliance)

| Property | Requirement | Implementation |
| :--- | :--- | :--- |
| **Aspect Ratio** | `9:16` (Vertical) | Full-screen mobile swipe format |
| **Resolution** | `1080 × 1920 px` | Native Full HD |
| **Video Codec** | `H.264` (`libx264`, `yuv420p`) | Universal cross-platform playback |
| **Audio Codec** | `AAC` (`192 kbps`) | Clean, punchy voiceover |
| **Frame Rate** | `30 fps` | Smooth animation & subtitle timing |
| **Duration** | `45 seconds` (35–60s) | Strict micro-learning budget (110–130 spoken words) |
| **Audio Loudness** | `-14 LUFS` Voice / `-22 dB` BGM | Auto-ducking speech mixer |
| **Subtitles** | Burned-in Kinetic | Amber (`#F59E0B`) active word highlight at `Y = 1400px` |
| **Safe Zones** | Top 120px & Bottom 320px | Zero collision with native mobile UI elements |

---

## 🧪 Running Automated Tests

Run the full verification test suites:
```bash
./venv/bin/python tests/test_phase1.py        # Config, DB, JWT Auth & Storage
./venv/bin/python tests/test_phase2.py        # Dual-Tier Agents, FactCheck & Gating
./venv/bin/python tests/test_phase3.py        # Audio Synthesis, PIL Cards & FFmpeg
./venv/bin/python tests/test_phase4.py        # Conceptly Core Ingestion Payloads
./venv/bin/python tests/test_api_endpoints.py # End-to-end 3-Gate HTTP API
```
