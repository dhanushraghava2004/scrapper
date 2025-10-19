# company_scraper.py
import argparse
import asyncio
import contextlib
import json
import re
import time
from typing import List, Dict, Any, Optional

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page



def run_company_scrape(company_url: str, long_mode: bool = False) -> dict:
    # TODO: call your existing scraping code
    data = {"company_url": company_url, "long_mode": long_mode, "ok": True}
    return data




# was: 9000 / 3500
NAV_TIMEOUT_MS = 30000         # 30s for page.goto & navigations
ACTION_TIMEOUT_MS = 10000      # 10s for selectors/clicks
SCROLL_WAIT_BETWEEN = 0.30


# ------------------------- Faster defaults -------------------------

# NAV_TIMEOUT_MS = 9000        # navigation timeouts
# ACTION_TIMEOUT_MS = 3500     # locator waits, clicks, selectors
# SCROLL_WAIT_BETWEEN = 0.25   # seconds between scrolls

# ------------------------- Utils -------------------------

def clean_text(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = s.replace("\r", "")
    lines = [ln.strip() for ln in s.split("\n")]
    out_lines = []
    for ln in lines:
        if ln == "" and (len(out_lines) == 0 or out_lines[-1] == ""):
            continue
        out_lines.append(ln)
    return "\n".join(out_lines).strip()

async def goto_resilient(page: Page, url: str) -> None:
    # try quick path first
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        return
    except Exception:
        pass
    # second try: longer & 'load'
    try:
        await page.goto(url, wait_until="load", timeout=30000)
        return
    except Exception:
        pass
    # last try: no wait_until, then explicitly wait for something we expect
    await page.goto(url, timeout=30000)
    with contextlib.suppress(Exception):
        await page.wait_for_selector("main, body", timeout=10000)

async def scroll_to_load(
    page: Page,
    scroll_runs: int = 10,
    wait_between: float = SCROLL_WAIT_BETWEEN,
    stop_when_selector: Optional[str] = None,
    stop_count: Optional[int] = None,
):
    prev_height = None
    stagnant = 0
    for _ in range(scroll_runs):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(wait_between)

        if stop_when_selector and stop_count:
            with contextlib.suppress(Exception):
                cnt = await page.locator(stop_when_selector).count()
                if cnt >= stop_count:
                    break

        try:
            cur_height = await page.evaluate("document.body.scrollHeight")
        except Exception:
            cur_height = None

        if prev_height == cur_height:
            stagnant += 1
            if stagnant >= 2:
                break
        else:
            stagnant = 0
        prev_height = cur_height

async def _gather_texts(locator) -> List[str]:
    texts: List[str] = []
    with contextlib.suppress(Exception):
        raws = await locator.all_inner_texts()
        for raw in raws:
            for chunk in raw.splitlines():
                value = chunk.strip()
                if value:
                    texts.append(value)
    seen = set()
    out = []
    for t in texts:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out

async def _safe_text(locator) -> Optional[str]:
    with contextlib.suppress(Exception):
        txt = await locator.inner_text()
        txt = txt.strip()
        if txt:
            return txt
    return None

async def _safe_attribute(locator, attribute: str) -> Optional[str]:
    with contextlib.suppress(Exception):
        value = await locator.get_attribute(attribute)
        if value:
            return value.strip()
    return None

def ensure_trailing_slash(u: str) -> str:
    return u if u.endswith("/") else u + "/"

def company_root(url: str) -> str:
    m = re.search(r"(https?://(?:www\.)?linkedin\.com/company/[^/?#]+)", url)
    if m:
        return ensure_trailing_slash(m.group(1))
    return ensure_trailing_slash(url.split("?")[0])

def to_int(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"([\d,.]+)", text.replace(",", ""))
    try:
        return int(m.group(1)) if m else None
    except Exception:
        return None

# ------------------------- BASIC (Company top card) -------------------------

async def _scrape_company_basic(page: Page) -> Dict[str, Any]:
    # Name
    name = None
    for sel in [
        "h1.org-top-card-summary__title",
        ".top-card-layout__title",
        "[data-test-id='hero-title']",
        "main h1",
        "h1"
    ]:
        name = await _safe_text(page.locator(sel).first)
        if name:
            break

    # Tagline
    tagline = None
    for sel in [
        ".org-top-card-summary__tagline",
        ".top-card-layout__headline",
        "[data-test-id='hero-summary']",
        ".text-body-medium"
    ]:
        tagline = await _safe_text(page.locator(sel).first)
        if tagline:
            break

    # Followers
    followers_text = None
    for sel in [
        ".org-top-card-summary__follower-count",
        ".top-card-layout__first-subline",
        "a[href$='/followers/']",
        "div:has-text('followers')"
    ]:
        t = await _safe_text(page.locator(sel).first)
        if t and "followers" in t.lower():
            followers_text = t
            break
    followers = None
    if followers_text:
        followers = to_int(followers_text)

    # Employees on LinkedIn (from top card if present)
    employees_text = None
    for sel in [
        "a[href*='/people/']",
        "a:has-text('employees')",
        ".top-card-layout__second-subline",
        ".org-top-card-summary-info-list__info-item"
    ]:
        t = await _safe_text(page.locator(sel).first)
        if t and "employee" in t.lower():
            employees_text = t
            break
    employees_on_linkedin = to_int(employees_text) if employees_text else None

    return {
        "name": name,
        "tagline": tagline,
        "followers": followers,
        "employees_on_linkedin": employees_on_linkedin,
        "raw_followers_text": followers_text,
        "raw_employees_text": employees_text,
    }

# ------------------------- ABOUT (Company /about tab) -------------------------
ABOUT_LABELS = {
    "website": ["website"],
    "phone": ["phone"],
    "industry": ["industry"],
    "company_size": ["company size", "size"],
    "headquarters": ["headquarters"],
    "founded": ["founded"],
    "specialties": ["specialties"],
    "type": ["type"],
    "locations": ["locations"],
}

def _norm_label(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()

def _label_key(lbl: str) -> Optional[str]:
    l = _norm_label(lbl)
    for key, synonyms in ABOUT_LABELS.items():
        for syn in synonyms:
            if syn in l:
                return key
    return None

async def extract_company_about(page: Page, root: str) -> Dict[str, Any]:
    """
    Navigate to /about and return:
    {
      "description": "...",
      "fields": { website, industry, size, headquarters, founded, specialties, type, ... }
    }
    """
    about_url = root.rstrip("/") + "/about/"
    with contextlib.suppress(Exception):
        await goto_resilient(page, about_url)

    # Expand "See more" with Playwright (Playwright CAN use :has-text)
    with contextlib.suppress(Exception):
        sec = page.locator("section[aria-label='About'], section:has(h2)")
        if await sec.count() > 0:
            # click any visible 'See more' inside the About section
            btns = sec.first.locator(
                "button:has-text('See more'), button:has-text('Show more'), button[aria-expanded='false']"
            )
            for i in range(await btns.count()):
                b = btns.nth(i)
                if await b.is_visible():
                    with contextlib.suppress(Exception):
                        await b.click(timeout=1200)
                        await asyncio.sleep(0.1)

    # ------- Now parse with BeautifulSoup (NO :has-text anywhere) -------
    html = await page.content()
    soup = BeautifulSoup(html, "lxml")

    # Find the About section container:
    # 1) aria-label=About
    about_sec = soup.select_one("section[aria-label='About']")
    # 2) fallback: any <section> that contains an h2/h3 whose text contains 'About'
    if not about_sec:
        for sec in soup.select("section"):
            hdr = sec.find(["h2", "h3"])
            if hdr and re.search(r"\bAbout\b", hdr.get_text(strip=True), flags=re.I):
                about_sec = sec
                break
    # 3) final fallback: try a broader container
    if not about_sec:
        about_sec = soup.select_one("main") or soup

    # ----- Description -----
    description = None
    # Prefer paragraphs inside the about section
    for p in about_sec.select("p"):
        txt = clean_text(p.get_text())
        if txt and len(txt) > 40:
            description = txt
            break
    # Secondary guesses
    if not description:
        for css in [
            "[data-test-id='about-us__description']",
            ".org-grid__core-rail p",
            ".break-words"
        ]:
            el = about_sec.select_one(css) or soup.select_one(css)
            if el and clean_text(el.get_text()):
                description = clean_text(el.get_text())
                break
    # Fallback: pick the longest paragraph on the page
    if not description:
        paras = [clean_text(p.get_text()) for p in about_sec.select("p")]
        paras = [p for p in paras if p and len(p) > 60]
        if paras:
            description = max(paras, key=len)

    # ----- Fields (Website, Industry, Size, etc.) -----
    fields: Dict[str, Any] = {}

    # Prefer <dl><dt>/<dd> pairs within the about section
    dl = about_sec.select_one("dl") or soup.select_one("section[aria-label='About'] dl")
    if dl:
        dts = [clean_text(x.get_text()) for x in dl.select("dt")]
        dds = [clean_text(x.get_text()) for x in dl.select("dd")]
        n = min(len(dts), len(dds))
        for i in range(n):
            key = _label_key(dts[i] or "")
            val = dds[i]
            if key and val:
                fields[key] = val

    # If still sparse, scan list rows like "Website: example.com"
    if not fields:
        rows = about_sec.select("li")
        for r in rows:
            txt = clean_text(r.get_text()) or ""
            if ":" in txt:
                label, val = txt.split(":", 1)
                key = _label_key(label)
                val = clean_text(val)
                if key and val:
                    fields[key] = val

    # Try to capture website if still missing (prefer first non-LinkedIn external link)
    if "website" not in fields:
        for a in about_sec.select("a[href]"):
            href = a.get("href", "")
            if href.startswith("http") and "linkedin.com" not in href:
                fields["website"] = clean_text(href)
                break

    return {
        "description": description,
        "fields": fields
    }


# ------------------------- PEOPLE (Company /people tab) -------------------------

async def extract_company_people(page: Page, root: str) -> Dict[str, Any]:
    people_url = root + "people/"
    with contextlib.suppress(Exception):
        await goto_resilient(page, people_url)
        await page.wait_for_selector("main, section", timeout=ACTION_TIMEOUT_MS)

    text_blobs = await _gather_texts(page.locator("main, section"))
    employees_on_linkedin = None
    for t in text_blobs:
        # e.g., "All employees (1,234)"
        m = re.search(r"employees?\s*\(?([\d,\.]+)\)?", t, flags=re.I)
        if m:
            try:
                employees_on_linkedin = int(m.group(1).replace(",", ""))
                break
            except Exception:
                continue

    return {"employees_on_linkedin": employees_on_linkedin}

# ------------------------- POSTS (Company /posts tab) -------------------------

def _post_key(post: Dict[str, Any]) -> tuple:
    return (
        post.get("text") or "",
        post.get("date") or "",
        tuple(post.get("media") or ()),
    )

async def extract_company_posts(page: Page, root: str, max_posts: int = -1) -> List[Dict[str, Any]]:
    posts_url = root + "posts/"
    with contextlib.suppress(Exception):
        await goto_resilient(page, posts_url)
        await page.wait_for_selector(
            "div.occludable-update, div.feed-shared-update-v2, article.feed-shared-update, div.feed-shared-update",
            timeout=ACTION_TIMEOUT_MS
        )

    posts: List[Dict[str, Any]] = []
    seen = set()
    stagnant = 0
    last_len = 0
    max_cycles = 120

    for _ in range(max_cycles):
        await scroll_to_load(page, scroll_runs=1, wait_between=SCROLL_WAIT_BETWEEN)

        html = await page.content()
        soup = BeautifulSoup(html, "lxml")

        post_nodes = soup.select("div.occludable-update, div.feed-shared-update-v2, article.feed-shared-update")
        if not post_nodes:
            post_nodes = soup.select("div.feed-shared-update")

        for p in post_nodes:
            text_el = p.select_one(".feed-shared-update-v2__description, .feed-shared-text, .update-components-text")
            text = clean_text(text_el.get_text()) if text_el else clean_text(p.get_text())
            if text and len(text) < 5:
                continue
            date_el = p.select_one("span.feed-shared-actor__meta, span.feed-shared-actor__sub-description, time")
            date = clean_text(date_el.get_text()) if date_el else None
            react_el = p.select_one(".social-details-social-counts__reactions-count, .social-details-social-counts__reactions, button[data-control-name='likes_count']")
            reactions = clean_text(react_el.get_text()) if react_el else None
            comm_el = p.select_one(".social-details-social-counts__comments, button[data-control-name='comments_count']")
            comments = clean_text(comm_el.get_text()) if comm_el else None

            medias = []
            for img in p.select("img"):
                src = img.get("src")
                if src and "profile" not in src and len(src) > 10:
                    medias.append(src)

            post = {
                "text": text,
                "date": date,
                "reactions": reactions,
                "comments_count": comments,
                "media": list(dict.fromkeys(medias)),
                "raw_html_snippet": clean_text(str(p)[:2000])
            }
            key = _post_key(post)
            if key not in seen and (post.get("text") or "").strip():
                seen.add(key)
                posts.append(post)

        if max_posts > 0 and len(posts) >= max_posts:
            posts = posts[:max_posts]
            break

        if len(posts) == last_len:
            stagnant += 1
        else:
            stagnant = 0
        last_len = len(posts)

        if max_posts < 0 and stagnant >= 6:
            break

    return posts

# ------------------------- Main -------------------------

async def scrape_company(url: str, storage_state: str, *, headful: bool = False, block_media: bool = False, all_posts: bool = False, max_posts: int = 50) -> Dict[str, Any]:
    root = company_root(url)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not headful)
        context = await browser.new_context(storage_state=storage_state)
        context.set_default_timeout(ACTION_TIMEOUT_MS)
        
        if block_media:
            async def _block_media(route):
                r = route.request
                if r.resource_type in {"image", "media", "font"}:
                    await route.abort()
                else:
                    await route.continue_()
            await context.route("**/*", _block_media)

        
        
        page = await context.new_page()
        page.set_default_timeout(ACTION_TIMEOUT_MS)
        page.set_default_navigation_timeout(NAV_TIMEOUT_MS)

        # if block_media:
        #     await context.route("**/*", lambda route: route.abort() if route.request.resource_type in {"image","media","font"} else route.continue_())

        # Hit the root company page first
        await goto_resilient(page, root)
        with contextlib.suppress(Exception):
            await page.wait_for_selector("main", timeout=3500)
        with contextlib.suppress(Exception):
            await page.wait_for_selector("h1", timeout=3500)

        if "login" in page.url and "linkedin.com" in page.url:
            raise RuntimeError("LinkedIn requires login. Ensure your storage_state is valid and logged-in.")

        # Canonical URL
        canonical_url: Optional[str] = None
        with contextlib.suppress(Exception):
            canonical_url = await page.eval_on_selector("link[rel='canonical']", "el => el.href")
        company_url = (canonical_url or page.url or root).split("?")[0]
        root = company_root(company_url)

        # Basic (top card)
        basic = await _scrape_company_basic(page)

        # About (description + fields)
        about = await extract_company_about(page, root)

        # People (employee count fallback)
        people = await extract_company_people(page, root)
        if not basic.get("employees_on_linkedin") and people.get("employees_on_linkedin"):
            basic["employees_on_linkedin"] = people["employees_on_linkedin"]

        # Posts
        posts_cap = -1 if all_posts else max_posts
        try:
            posts = await extract_company_posts(page, root, max_posts=posts_cap)
        except Exception:
            posts = []

        profile: Dict[str, Any] = {
            "input_url": url,
            "company_url": company_url,
            "basic": basic,
            "about": about,
            "people": people,
            "posts": posts,
            "scrape_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        await browser.close()
        return profile

def parse_args():
    p = argparse.ArgumentParser(description="Scrape LinkedIn company pages (basic, about, people, posts)")
    p.add_argument("--url", required=True, help="LinkedIn company URL (e.g., https://www.linkedin.com/company/<slug>/)")
    p.add_argument("--storage", required=True, help="Playwright storage_state.json (logged-in session)")
    p.add_argument("--all-posts", action="store_true", help="Fetch ALL company posts (scroll until no more)")
    p.add_argument("--max-posts", type=int, default=50, help="Cap number of posts (ignored if --all-posts)")
    p.add_argument("--output", default="company_profile.json", help="Output JSON file")
    p.add_argument("--headful", action="store_true", help="Run headed browser (debugging)")
    p.add_argument("--block-media", action="store_true", help="Block images/media/fonts (faster; no post images)")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    data = asyncio.run(
        scrape_company(
            args.url,
            args.storage,
            headful=args.headful,
            block_media=args.block_media,
            all_posts=args.all_posts,
            max_posts=args.max_posts
        )
    )
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("Saved to", args.output)
    print(json.dumps({
        "company": data.get("basic", {}).get("name"),
        "tagline": data.get("basic", {}).get("tagline"),
        "followers": data.get("basic", {}).get("followers"),
        "employees_on_linkedin": data.get("basic", {}).get("employees_on_linkedin"),
    }, indent=2, ensure_ascii=False))
