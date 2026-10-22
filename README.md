# Conceptly Studio 🎬🤖

Autonomous AI agent factory for generating high-retention 9:16 vertical educational reels and syncing them directly to the Conceptly platform.

## Quick Start

### 1. Prerequisites
- Python 3.9+ installed
- FFmpeg installed (`brew install ffmpeg` on macOS)

### 2. Setup Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment Variables
Copy `.env.example` to `.env` and fill in your API keys:
```bash
cp .env.example .env
```

### 4. Generate a Test Reel
```bash
python -m src.cli --topic "Newton's Third Law" --class-level 9 --subject "Physics"
```

## Architecture & Contracts
- See [architecture.md](architecture.md) for the complete multi-agent pipeline specification.
- See [STUDIO_INTEGRATION_CONTRACT.md](STUDIO_INTEGRATION_CONTRACT.md) for the universal domain taxonomy, video specs, and Conceptly API integration schemas.
