from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import os

# import your wrappers
from Profile_scrapper import run_profile_scrape
from Company_scrapper import run_company_scrape

API_KEY = os.getenv("API_KEY", "change-me")  # set this on Cloud Run later

app = FastAPI()

class ProfileIn(BaseModel):
    url: str

class CompanyIn(BaseModel):
    url: str
    long_mode: bool = False

@app.get("/healthz")
def health():
    return {"ok": True}

@app.post("/profile")
def profile(inp: ProfileIn, x_api_key: str | None = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = run_profile_scrape(inp.url)
    return result

@app.post("/company")
def company(inp: CompanyIn, x_api_key: str | None = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    result = run_company_scrape(inp.url, inp.long_mode)
    return result
