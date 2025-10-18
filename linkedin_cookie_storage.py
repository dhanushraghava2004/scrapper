# save_linkedin_storage.py
import asyncio
from playwright.async_api import async_playwright
import sys

async def run(headful=True, out="storage_state.json"):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not headful)
        context = await browser.new_context()
        page = await context.new_page()
        print("Opening LinkedIn login. Please log in manually in the browser window.")
        await page.goto("https://www.linkedin.com/login")
        print("After login completes, press Enter here to save storage state.")
        input()
        await context.storage_state(path=out)
        print(f"Saved storage state to {out}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
