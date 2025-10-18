# app.py
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import os, json, tempfile
from Profile_scrapper import scrape_profile

API_KEY = os.getenv("API_KEY", "change-me")
DEFAULT_STORAGE_PATH = os.getenv("STORAGE_FILE", "/etc/secrets/storage_state.json")

app = FastAPI()

class ProfileIn(BaseModel):
    url: str
    # choose exactly ONE of these ways to provide storage:
    storage: str | None = None          # path inside container, default below
    storage_b64: str | None = None      # base64 of storage_state.json (optional)
    # other options with good defaults
    all_posts: bool = False
    max_posts: int = 50
    headful: bool = False
    block_media: bool = False

@app.post("/profile")
async def profile(inp: ProfileIn, x_api_key: str | None = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # decide where storage_state.json comes from
    storage_path = inp.storage or DEFAULT_STORAGE_PATH
    if inp.storage_b64:
        # n8n can send base64; write to a temp file just for this run
        import base64, os
        fd, tmp = tempfile.mkstemp(suffix=".json")
        os.write(fd, base64.b64decode(inp.storage_b64))
        os.close(fd)
        storage_path = tmp

    max_posts = -1 if inp.all_posts else inp.max_posts

    data = await scrape_profile(
        inp.url,
        storage_path,
        max_posts=max_posts,
        headful=inp.headful,
        block_media=inp.block_media
    )
    return data
