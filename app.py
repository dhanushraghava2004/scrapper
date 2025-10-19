# app.py
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import os, tempfile, base64, traceback
import traceback, contextlib
from Profile_scrapper import scrape_profile  # <- ensure file is exactly Profile_scrapper.py and function name matches

# TOP of app.py before other imports that might touch asyncio
import sys, asyncio
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass


API_KEY = os.getenv("API_KEY", "change-me")
DEFAULT_STORAGE_PATH = os.getenv("STORAGE_FILE", r"D:\NEO\linkedin_scrapper\storage_state.json")

app = FastAPI()


# Health endpoints
@app.get("/")
def root():
    return {"ok": True, "service": "scrapper"}

@app.api_route("/healthz", methods=["GET", "HEAD", "POST"])
def healthz():
    return {"ok": True}

class ProfileIn(BaseModel):
    url: str
    storage: str | None = None
    storage_b64: str | None = None
    all_posts: bool = False
    max_posts: int = 50
    headful: bool = False
    block_media: bool = False


@app.post("/profile")
async def profile(inp: ProfileIn, x_api_key: str | None = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    storage_path = inp.storage or DEFAULT_STORAGE_PATH
    tmp_path = None
    if inp.storage_b64:
        fd, tmp_path = tempfile.mkstemp(suffix=".json")
        os.write(fd, base64.b64decode(inp.storage_b64))
        os.close(fd)
        storage_path = tmp_path

    try:
        if not storage_path or not os.path.exists(storage_path):
            raise FileNotFoundError(storage_path or "(empty path)")

        max_posts = -1 if inp.all_posts else inp.max_posts
        data = await scrape_profile(
            inp.url,
            storage_path,
            max_posts=max_posts,
            headful=inp.headful,
            block_media=inp.block_media
        )
        return data

    except Exception as e:
        # Print full traceback to the server console AND return readable detail
        print("SERVER ERROR:\n", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            with contextlib.suppress(Exception):
                os.remove(tmp_path)

from Company_scrapper import scrape_company  # <-- file name must match

class CompanyIn(BaseModel):
    url: str
    storage: str | None = None
    storage_b64: str | None = None
    headful: bool = False
    block_media: bool = True
    all_posts: bool = False
    max_posts: int = 50

@app.post("/company")
async def company(inp: CompanyIn, x_api_key: str | None = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

    storage_path = inp.storage or DEFAULT_STORAGE_PATH
    tmp_path = None
    if inp.storage_b64:
        fd, tmp_path = tempfile.mkstemp(suffix=".json")
        os.write(fd, base64.b64decode(inp.storage_b64))
        os.close(fd)
        storage_path = tmp_path

    import asyncio, contextlib, traceback
    try:
        if not storage_path or not os.path.exists(storage_path):
            raise FileNotFoundError(storage_path or "(empty path)")

        data = await asyncio.wait_for(
            scrape_company(
                inp.url,
                storage_state=storage_path,
                headful=inp.headful,
                block_media=inp.block_media,
                all_posts=inp.all_posts,
                max_posts=inp.max_posts,
            ),
            timeout=90
        )
        return data

    except asyncio.TimeoutError:
        raise HTTPException(504, "Company scrape timed out (90s)")
    except FileNotFoundError as e:
        raise HTTPException(400, f"Storage file not found: {e}")
    except RuntimeError as e:
        raise HTTPException(401, str(e))
    except Exception as e:
        print("SERVER ERROR:\n", traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            with contextlib.suppress(Exception):
                os.remove(tmp_path)

