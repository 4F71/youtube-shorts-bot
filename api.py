# ============================================================
# api.py — FastAPI HTTP Wrapper
# n8n bu endpoint'e POST atır → pipeline async olarak çalışır.
#
# Endpoints:
#   POST /run          → Pipeline start
#   GET  /status       → Last pipeline status
#   GET  /quota        → ElevenLabs quota check
#   GET  /history      → Recent uploads
# ============================================================

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query
from pydantic import BaseModel

from main import load_config

app = FastAPI(title="YouTube Shorts Bot API", version="1.0")

# Config
CONFIG_PATH = os.environ.get("CONFIG_PATH", "config/config.yaml")
HISTORY_FILE = "output/history.jsonl"

# Pipeline state tracking
_pipeline_state = {
    "running": False,
    "last_result": None,
    "started_at": None,
}


# ─── Request / Response Models ────────────────────────────
class RunRequest(BaseModel):
    category: Optional[str] = None   # "story_hook" | "model_battle" | "ai_lies"
    dry_run: bool = False


class RunResponse(BaseModel):
    status: str
    message: str
    video_id: Optional[str] = None


# ─── POST /run ────────────────────────────────────────────
@app.post("/run", response_model=RunResponse)
async def run_pipeline_endpoint(req: RunRequest):
    """Pipeline trigger — n8n buraya POST atar"""

    if _pipeline_state["running"]:
        return RunResponse(
            status="busy",
            message="Pipeline already running. Wait for completion.",
        )

    # Validate category
    valid_categories = ["story_hook", "model_battle", "ai_lies", None]
    if req.category not in valid_categories:
        return RunResponse(status="error", message=f"Invalid category: {req.category}")

    # Async start
    _pipeline_state["running"] = True
    _pipeline_state["started_at"] = datetime.now().isoformat()

    # Fire and forget — pipeline runs in background
    asyncio.create_task(_run_background(req))

    return RunResponse(
        status="started",
        message=f"Pipeline started. Category: {req.category or 'auto (round-robin)'}",
    )


async def _run_background(req: RunRequest):
    """Background pipeline runner — runs main() in a thread executor"""
    import concurrent.futures
    import sys

    loop = asyncio.get_event_loop()
    try:
        def _sync_main():
            old_argv = sys.argv[:]
            if req.category:
                sys.argv = ["main.py", "--category", req.category]
            try:
                from main import main
                main()
                return {"success": True}
            except SystemExit as e:
                return {"success": e.code == 0, "exit_code": e.code}
            finally:
                sys.argv = old_argv

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            result = await loop.run_in_executor(executor, _sync_main)

        _pipeline_state["last_result"] = result
    except Exception as e:
        _pipeline_state["last_result"] = {"error": str(e), "success": False}
    finally:
        _pipeline_state["running"] = False


# ─── GET /status ──────────────────────────────────────────
@app.get("/status")
async def get_status():
    """Current pipeline state"""
    return {
        "running": _pipeline_state["running"],
        "started_at": _pipeline_state["started_at"],
        "last_result": _pipeline_state["last_result"],
    }


# ─── GET /quota ───────────────────────────────────────────
@app.get("/quota")
async def get_quota():
    """ElevenLabs quota check"""
    try:
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            return {"error": "ELEVENLABS_API_KEY not configured"}
        from elevenlabs import ElevenLabs
        client = ElevenLabs(api_key=api_key)
        subscription = client.user.get_subscription()
        return {
            "character_count": subscription.character_count,
            "character_limit": subscription.character_limit,
            "characters_remaining": subscription.character_limit - subscription.character_count,
        }
    except Exception as e:
        return {"error": str(e)}


# ─── GET /history ─────────────────────────────────────────
@app.get("/history")
async def get_history(limit: int = Query(default=10, le=50)):
    """Recent pipeline history"""
    if not os.path.exists(HISTORY_FILE):
        return {"entries": []}

    with open(HISTORY_FILE, "r") as f:
        lines = f.readlines()

    entries = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return {"entries": entries, "total": len(lines)}


# ─── GET /health ──────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}