#!/usr/bin/env python3
"""
linkedin_profile_scraper.py
Usage:
  python linkedin_profile_scraper.py --url "https://www.linkedin.com/in/xxxx/" --storage storage_state.json --max-posts 50 --output out.json --headful

#   """
# import argparse
# import asyncio
# import contextlib
# import json
# import time
# import re
# from typing import List, Dict, Any, Optional

# from bs4 import BeautifulSoup
# from playwright.async_api import async_playwright, Page

# # ------------------------- Utils -------------------------

# def clean_text(s: Optional[str]) -> Optional[str]:
#     if not s:
#         return None
#     return " ".join(s.split()).strip()

# async def scroll_to_load(page: Page, scroll_runs: int = 15, wait_between: float = 0.8):
#     prev_height = None
#     for _ in range(scroll_runs):
#         await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
#         await asyncio.sleep(wait_between)
#         cur_height = await page.evaluate("document.body.scrollHeight")
#         if prev_height == cur_height:
#             break
#         prev_height = cur_height

# # Helpers commonly used across extractors
# async def _gather_texts(locator) -> List[str]:
#     texts: List[str] = []
#     with contextlib.suppress(Exception):
#         raw_texts = await locator.all_inner_texts()
#         for raw in raw_texts:
#             for chunk in raw.splitlines():
#                 value = chunk.strip()
#                 if value:
#                     texts.append(value)
#     # de-dupe preserving order
#     seen = set()
#     out = []
#     for t in texts:
#         if t not in seen:
#             seen.add(t)
#             out.append(t)
#     return out

# async def _safe_text(locator) -> Optional[str]:
#     with contextlib.suppress(Exception):
#         txt = await locator.inner_text()
#         txt = txt.strip()
#         if txt:
#             return txt
#     return None

# async def _safe_attribute(locator, attribute: str) -> Optional[str]:
#     with contextlib.suppress(Exception):
#         value = await locator.get_attribute(attribute)
#         if value:
#             return value.strip()
#     return None

# # ------------------------- BASIC INFO + ABOUT -------------------------

# PRONOUN_TOKENS = {
#     "he/him", "she/her", "they/them", "he • him", "she • her", "they • them"
# }

# def _pick_location(candidates: List[str]) -> Optional[str]:
#     """Choose the most location-like string (skip pronouns)."""
#     for c in candidates:
#         t = (c or "").strip()
#         if not t:
#             continue
#         tl = t.lower()
#         if tl in PRONOUN_TOKENS:
#             continue
#         # Favor city/country-like strings
#         if ("," in t) or any(k in tl for k in [
#             "india","united","usa","uk","uae","germany","canada","australia",
#             "hyderabad","bengaluru","mumbai","delhi","pune","chennai",
#             "gurgaon","noida","kolkata","ahmedabad","coimbatore",
#             "trivandrum","vizag","mysuru"
#         ]):
#             return t
#     # Fallback: first non-pronoun token
#     for t in candidates:
#         tl = (t or "").lower().strip()
#         if tl and tl not in PRONOUN_TOKENS:
#             return t
#     return None


# # ===== BASIC INFO: extractor =====
# async def _scrape_basic_profile(page: Page) -> Dict[str, Any]:
#     # Name: try multiple selectors before falling back to JSON-LD or the page title.
#     name = None
#     name_selectors = [
#         "section.pv-top-card h1",
#         "[data-view-name='identity-component'] h1",
#         "main h1",
#         "main h1.text-heading-xlarge",
#         ".top-card-layout__entity-info h1",
#         ".top-card-layout__title",
#         ".text-heading-xlarge",
#         "[data-test-id='hero-title']",
#         "[data-test-id='profile-card-full-name']",
#         ".profile-top-card__name",
#     ]
#     for selector in name_selectors:
#         name = await _safe_text(page.locator(selector).first)
#         if name:
#             break

#     if not name:
#         with contextlib.suppress(Exception):
#             ld_jsons = await page.eval_on_selector_all(
#                 "script[type='application/ld+json']",
#                 "els => els.map(e => e.textContent)"
#             )
#             for raw in ld_jsons:
#                 with contextlib.suppress(Exception):
#                     data = json.loads(raw)
#                     if isinstance(data, dict) and data.get("@type") == "Person":
#                         name = data.get("name")
#                         break
#                     if isinstance(data, list):
#                         for d in data:
#                             if isinstance(d, dict) and d.get("@type") == "Person":
#                                 name = d.get("name")
#                                 break
#                 if name:
#                     break

#     if not name:
#         with contextlib.suppress(Exception):
#             title = await page.title()
#             if title:
#                 name = title.split(" | ")[0].strip()

#     # Headline
#     headline = None
#     headline_selectors = [
#         "div.text-body-medium.break-words",
#         "[data-view-name='identity-component'] .text-body-medium",
#         ".pv-top-card span[dir='ltr']",
#         ".top-card-layout__headline",
#         ".text-body-medium",
#         "[data-test-id='hero-summary']",
#         ".profile-top-card__headline",
#     ]
#     for selector in headline_selectors:
#         headline = await _safe_text(page.locator(selector).first)
#         if headline:
#             break

#     # Location (collect candidates, pick best)
#     location = None
#     location_selectors = [
#         "section.pv-top-card span.text-body-small",
#         ".pv-text-details__left-panel span.text-body-small",
#         ".top-card-layout__first-subline span",
#         ".text-body-small.inline.t-black--light.break-words",
#         "[data-test-id='hero-location']",
#         ".profile-top-card__location",
#         ".profile-topcard__location-data",
#     ]
#     for selector in location_selectors:
#         candidate = await _safe_text(page.locator(selector).first)
#         if candidate and candidate.strip().lower() not in PRONOUN_TOKENS:
#             location = candidate.strip()
#             break

#     loc_candidates: List[str] = []
#     for sel in [
#         "div.pv-text-details__left-panel span.text-body-small",
#         "[data-view-name='identity-component'] .text-body-small",
#         ".pv-top-card--list-bullet li",
#         "[data-test-id='hero-location']",
#         ".profile-top-card__location",
#         ".profile-topcard__location-data",
#     ]:
#         with contextlib.suppress(Exception):
#             loc_candidates.extend(await _gather_texts(page.locator(sel)))
#     if not location:
#         location = _pick_location(loc_candidates)

#     # Details (right-panel chips - pronouns, etc.)
#     details = await _gather_texts(page.locator("ul.pv-text-details__right-panel"))

#     return {
#         "name": name.strip() if name else None,
#         "headline": headline,
#         "location": location,
#         "details": details or [],
#     }
# # ===== BASIC INFO: extractor (end) =====



# # ===== ABOUT: extractor =====
# async def extract_about(page: Page) -> Optional[str]:
#     selectors = [
#         "section#about",
#         "[data-view-name='about']",
#         "section[data-test-id='about']",
#     ]
#     section = None
#     for sel in selectors:
#         loc = page.locator(sel)
#         if await loc.count() > 0:
#             section = loc.first
#             break
#     if section is None:
#         return None

#     with contextlib.suppress(Exception):
#         await section.scroll_into_view_if_needed()
#         await page.wait_for_timeout(200)

#     with contextlib.suppress(Exception):
#         buttons = section.get_by_role("button", name=re.compile(r"(see|show)\s+more", re.I))
#         for idx in range(await buttons.count()):
#             btn = buttons.nth(idx)
#             with contextlib.suppress(Exception):
#                 if await btn.is_visible():
#                     await btn.click()
#                     await page.wait_for_timeout(350)

#     text_selectors = [
#         ".inline-show-more-text span[aria-hidden='false']",
#         ".inline-show-more-text span:not([aria-hidden='true'])",
#         "[data-test-id='text-block'] span[aria-hidden='false']",
#         "div[data-test-id='text-with-see-more'] span[aria-hidden='false']",
#         ".pvs-list__outer-container span[aria-hidden='true']",
#         ".pvs-list__outer-container span:not([aria-hidden='true'])",
#         "p",
#     ]
#     for sel in text_selectors:
#         txt = await _safe_text(section.locator(sel).first)
#         if txt:
#             cleaned = clean_text(txt.replace("About", "", 1))
#             if cleaned:
#                 return cleaned

#     fallback = await _safe_text(section)
#     if fallback:
#         cleaned = clean_text(fallback.replace("About", "", 1))
#         if cleaned:
#             return cleaned

#     html = await page.content()
#     soup = BeautifulSoup(html, "lxml")
#     about_sec = soup.select_one("section#about, [data-view-name='about'], section[data-test-id='about']")
#     if about_sec:
#         rich = about_sec.select_one(".inline-show-more-text span[aria-hidden='false']")
#         if rich and clean_text(rich.get_text()):
#             return clean_text(rich.get_text())
#         txt = clean_text(about_sec.get_text())
#         if txt:
#             return clean_text(txt.replace("About", "", 1))
#     alt = soup.select_one(".pv-about__summary-text, .display-flex .inline-show-more-text")
#     return clean_text(alt.get_text()) if alt else None
# # ===== ABOUT: extractor (end) =====


# # ------------------------- Other sections (your originals) -------------------------

# async def extract_section_list(page: Page, section_id_marker: str) -> List[Dict[str, Any]]:
#     html = await page.content()
#     soup = BeautifulSoup(html, "lxml")
#     sections: List[Dict[str, Any]] = []
#     seen: set[tuple[str, str, str]] = set()

#     def pick_text(node, selectors: List[str]) -> Optional[str]:
#         for selector in selectors:
#             found = node.select_one(selector)
#             if not found:
#                 continue
#             text_val = clean_text(found.get_text())
#             if text_val:
#                 return text_val
#         return None

#     def register_entry(title: Optional[str], subtitle: Optional[str], date: Optional[str], raw: Optional[str]) -> None:
#         if not raw:
#             return
#         key = (
#             (title or '').lower(),
#             (subtitle or '').lower(),
#             (date or '').lower(),
#         )
#         if not any(key):
#             return
#         if key in seen:
#             return
#         seen.add(key)
#         sections.append({
#             'title': title,
#             'subtitle': subtitle,
#             'date': date,
#             'raw_html': raw,
#         })

#     def parse_item(node) -> None:
#         if not node:
#             return
#         title = pick_text(node, [
#             ".mr1.hoverable-link-text span[aria-hidden='true']",
#             ".mr1.hoverable-link-text.t-bold span[aria-hidden='true']",
#             ".mr1.hoverable-link-text span",
#             ".t-bold span[aria-hidden='true']",
#             ".t-bold[aria-hidden='true']",
#             ".t-bold",
#             "h3",
#             "h4",
#         ])
#         subtitle = pick_text(node, [
#             ".t-14.t-normal span[aria-hidden='true']",
#             ".t-14.t-normal",
#             ".pvs-entity__path-node span.t-14",
#             ".pv-entity__secondary-title",
#             ".pvs-entity__subtitle",
#             "h4.t-14",
#             "p",
#         ])
#         date = pick_text(node, [
#             "span.t-14.t-normal.t-black--light span[aria-hidden='true']",
#             "span.t-14.t-normal.t-black--light",
#             ".pv-entity__date-range span:nth-of-type(2)",
#             "time",
#         ])
#         raw = clean_text(node.get_text())
#         register_entry(title, subtitle, date, raw)

#         for nested_list in node.select("ul, ol"):
#             for nested_item in nested_list.find_all('li', recursive=False):
#                 parse_item(nested_item)

#     heading = soup.find(lambda tag: tag.name in ['h2', 'h3'] and section_id_marker.lower() in tag.get_text().lower())
#     section = heading.find_parent('section') if heading else None
#     if not section:
#         section = soup.select_one(f"section[id*='{section_id_marker}'], section[aria-label*='{section_id_marker}']")
#     if not section:
#         return sections

#     candidates = section.select('li.pvs-list__item, li.pvs-list__item--line-separated, li.artdeco-list__item')
#     if not candidates:
#         candidates = section.find_all('li')

#     for node in candidates:
#         parse_item(node)

#     return sections

# async def extract_skills(page: Page) -> List[str]:
#     html = await page.content()
#     soup = BeautifulSoup(html, "lxml")
#     skills: List[str] = []
#     for s in soup.select(".pv-skill-category-entity__name, .skill-pill, .pv-skill-category-entity__skill"):
#         txt = clean_text(s.get_text())
#         if txt:
#             skills.append(txt)
#     if not skills:
#         for s in soup.select(".skill"):
#             txt = clean_text(s.get_text())
#             if txt:
#                 skills.append(txt)
#     return list(dict.fromkeys(skills))

# async def extract_posts(page: Page, max_posts=50) -> List[Dict[str, Any]]:
#     if max_posts <= 0:
#         return []

#     posts: List[Dict[str, Any]] = []
#     try:
#         loc = page.url.rstrip("/")
#         activity_url = loc + "/detail/recent-activity/shares/"
#         await page.goto(activity_url)
#         await page.wait_for_timeout(1200)
#     except Exception:
#         pass

#     scroll_passes = 10
#     if max_posts > 30:
#         scroll_passes = 22
#     elif max_posts > 10:
#         scroll_passes = 14

#     await scroll_to_load(page, scroll_runs=scroll_passes, wait_between=0.65)

#     html = await page.content()
#     soup = BeautifulSoup(html, "lxml")

#     post_selectors = soup.select("div.occludable-update, div.feed-shared-update-v2, article.feed-shared-update")
#     if not post_selectors:
#         post_selectors = soup.select("div.feed-shared-update")

#     for p in post_selectors:
#         if len(posts) >= max_posts:
#             break
#         try:
#             text_el = p.select_one(".feed-shared-update-v2__description, .feed-shared-text, .update-components-text")
#             text = clean_text(text_el.get_text()) if text_el else clean_text(p.get_text())
#             date_el = p.select_one("span.feed-shared-actor__meta, span.feed-shared-actor__sub-description, time")
#             date = clean_text(date_el.get_text()) if date_el else None
#             react_el = p.select_one(".social-details-social-counts__reactions-count, .social-details-social-counts__reactions, button[data-control-name='likes_count']")
#             reactions = clean_text(react_el.get_text()) if react_el else None
#             comm_el = p.select_one(".social-details-social-counts__comments, button[data-control-name='comments_count']")
#             comments = clean_text(comm_el.get_text()) if comm_el else None

#             medias = []
#             for img in p.select("img"):
#                 src = img.get("src")
#                 if src and "profile" not in src and len(src) > 10:
#                     medias.append(src)

#             posts.append({
#                 "text": text,
#                 "date": date,
#                 "reactions": reactions,
#                 "comments_count": comments,
#                 "media": list(dict.fromkeys(medias)),
#                 "raw_html_snippet": clean_text(str(p)[:2000])
#             })
#         except Exception:
#             continue

#     # Deduplicate by (text, date, media)
#     deduped_posts: List[Dict[str, Any]] = []
#     seen_posts: set[tuple[str, Optional[str], tuple[str, ...]]] = set()
#     for post in posts:
#         text_val = post.get('text')
#         if not text_val:
#             continue
#         key = (
#             text_val,
#             post.get('date'),
#             tuple(post.get('media') or ()),
#         )
#         if key in seen_posts:
#             continue
#         seen_posts.add(key)
#         deduped_posts.append(post)

#     return deduped_posts

# # ------------------------- Main -------------------------


# async def scrape_profile(url: str, storage_state: str, max_posts: int = 50, headful: bool = False) -> Dict[str, Any]:
#     async with async_playwright() as p:
#         browser = await p.chromium.launch(headless=not headful)
#         context = await browser.new_context(storage_state=storage_state)
#         page = await context.new_page()
#         await page.goto(url, wait_until="domcontentloaded")
#         try:
#             await page.wait_for_selector("main", timeout=12000)
#             await page.wait_for_selector("main h1, h1.text-heading-xlarge", timeout=12000)
#         except Exception:
#             await page.wait_for_timeout(1500)

#         preload_scrolls = 4 if max_posts > 0 else 2
#         await scroll_to_load(page, scroll_runs=preload_scrolls, wait_between=0.45)
#         with contextlib.suppress(Exception):
#             await page.evaluate("window.scrollTo(0, 0)")

#         if "login" in page.url and "linkedin.com" in page.url:
#             raise RuntimeError("Looks like LinkedIn requires login. Ensure your storage state is valid and logged-in.")

#         canonical_url: Optional[str] = None
#         with contextlib.suppress(Exception):
#             canonical_url = await page.eval_on_selector("link[rel='canonical']", "el => el.href")
#         profile_url = (canonical_url or page.url or url).split("?")[0]

#         basic = await _scrape_basic_profile(page)
#         about = await extract_about(page)

#         profile: Dict[str, Any] = {
#             "input_url": url,
#             "profile_url": profile_url,
#             "name": basic.get("name"),
#             "headline": basic.get("headline"),
#             "location": basic.get("location"),
#             "details": basic.get("details"),
#             "about": about,
#         }

#         profile["experience"] = await extract_section_list(page, "experience")
#         profile["education"] = await extract_section_list(page, "education")
#         profile["skills"] = await extract_skills(page)

#         try:
#             posts = await extract_posts(page, max_posts=max_posts)
#         except Exception:
#             posts = []
#         profile["posts"] = posts

#         recent_activity_url = page.url
#         if recent_activity_url and recent_activity_url != profile_url:
#             profile["recent_activity_url"] = recent_activity_url
#         profile["scraped_url"] = profile_url
#         profile["scrape_timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")

#         await browser.close()
#         return profile

# def parse_args():
#     p = argparse.ArgumentParser()
#     p.add_argument("--url", required=True, help="LinkedIn profile URL")
#     p.add_argument("--storage", required=True, help="Playwright storage_state.json path (logged-in state)")
#     p.add_argument("--max-posts", type=int, default=50)
#     p.add_argument("--output", default="linkedin_profile.json")
#     p.add_argument("--headful", action="store_true", help="Run with headed browser (useful for debugging)")
#     return p.parse_args()

# if __name__ == "__main__":
#     args = parse_args()
#     data = asyncio.run(scrape_profile(args.url, args.storage, max_posts=args.max_posts, headful=args.headful))
#     with open(args.output, "w", encoding="utf-8") as f:
#         json.dump(data, f, indent=2, ensure_ascii=False)
#     print("Saved to", args.output)
#     print(json.dumps({k: data.get(k) for k in ("name", "headline", "about")}, indent=2, ensure_ascii=False))



# import argparse
# import asyncio
# import contextlib
# import json
# import time
# import re
# from typing import List, Dict, Any, Optional

# from bs4 import BeautifulSoup
# from playwright.async_api import async_playwright, Page

# # ------------------------- Faster defaults -------------------------

# NAV_TIMEOUT_MS = 9000        # navigation timeouts
# ACTION_TIMEOUT_MS = 3500     # locator waits, clicks, selectors
# SCROLL_WAIT_BETWEEN = 0.25   # seconds between scrolls

# # ------------------------- Utils -------------------------

# def clean_text(s: Optional[str]) -> Optional[str]:
#     if not s:
#         return None
#     return " ".join(s.split()).strip()

# async def scroll_to_load(
#     page: Page,
#     scroll_runs: int = 10,
#     wait_between: float = SCROLL_WAIT_BETWEEN,
#     stop_when_selector: Optional[str] = None,
#     stop_count: Optional[int] = None,
# ):
#     """
#     Fast, adaptive scroller:
#     - shorter waits
#     - stops when page height stops growing
#     - optional early stop when enough items are on the page
#     """
#     prev_height = None
#     stagnant = 0
#     for _ in range(scroll_runs):
#         await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
#         await asyncio.sleep(wait_between)

#         # Early stop: enough items?
#         if stop_when_selector and stop_count:
#             with contextlib.suppress(Exception):
#                 cnt = await page.locator(stop_when_selector).count()
#                 if cnt >= stop_count:
#                     break

#         try:
#             cur_height = await page.evaluate("document.body.scrollHeight")
#         except Exception:
#             cur_height = None

#         if prev_height == cur_height:
#             stagnant += 1
#             if stagnant >= 2:  # two stagnant checks in a row -> stop
#                 break
#         else:
#             stagnant = 0
#         prev_height = cur_height

# # Helpers commonly used across extractors
# async def _gather_texts(locator) -> List[str]:
#     texts: List[str] = []
#     with contextlib.suppress(Exception):
#         raw_texts = await locator.all_inner_texts()
#         for raw in raw_texts:
#             for chunk in raw.splitlines():
#                 value = chunk.strip()
#                 if value:
#                     texts.append(value)
#     # de-dupe preserving order
#     seen = set()
#     out = []
#     for t in texts:
#         if t not in seen:
#             seen.add(t)
#             out.append(t)
#     return out

# async def _safe_text(locator) -> Optional[str]:
#     with contextlib.suppress(Exception):
#         txt = await locator.inner_text()
#         txt = txt.strip()
#         if txt:
#             return txt
#     return None

# async def _safe_attribute(locator, attribute: str) -> Optional[str]:
#     with contextlib.suppress(Exception):
#         value = await locator.get_attribute(attribute)
#         if value:
#             return value.strip()
#     return None

# # ------------------------- BASIC INFO + ABOUT -------------------------

# PRONOUN_TOKENS = {
#     "he/him", "she/her", "they/them", "he • him", "she • her", "they • them"
# }

# def _pick_location(candidates: List[str]) -> Optional[str]:
#     """Choose the most location-like string (skip pronouns)."""
#     for c in candidates:
#         t = (c or "").strip()
#         if not t:
#             continue
#         tl = t.lower()
#         if tl in PRONOUN_TOKENS:
#             continue
#         # Favor city/country-like strings
#         if ("," in t) or any(k in tl for k in [
#             "india","united","usa","uk","uae","germany","canada","australia",
#             "hyderabad","bengaluru","mumbai","delhi","pune","chennai",
#             "gurgaon","noida","kolkata","ahmedabad","coimbatore",
#             "trivandrum","vizag","mysuru"
#         ]):
#             return t
#     # Fallback: first non-pronoun token
#     for t in candidates:
#         tl = (t or "").lower().strip()
#         if tl and tl not in PRONOUN_TOKENS:
#             return t
#     return None


# # ===== BASIC INFO: extractor =====
# async def _scrape_basic_profile(page: Page) -> Dict[str, Any]:
#     # Name: try multiple selectors before falling back to JSON-LD or the page title.
#     name = None
#     name_selectors = [
#         "section.pv-top-card h1",
#         "[data-view-name='identity-component'] h1",
#         "main h1",
#         "main h1.text-heading-xlarge",
#         ".top-card-layout__entity-info h1",
#         ".top-card-layout__title",
#         ".text-heading-xlarge",
#         "[data-test-id='hero-title']",
#         "[data-test-id='profile-card-full-name']",
#         ".profile-top-card__name",
#     ]
#     for selector in name_selectors:
#         name = await _safe_text(page.locator(selector).first)
#         if name:
#             break

#     if not name:
#         with contextlib.suppress(Exception):
#             ld_jsons = await page.eval_on_selector_all(
#                 "script[type='application/ld+json']",
#                 "els => els.map(e => e.textContent)"
#             )
#             for raw in ld_jsons:
#                 with contextlib.suppress(Exception):
#                     data = json.loads(raw)
#                     if isinstance(data, dict) and data.get("@type") == "Person":
#                         name = data.get("name")
#                         break
#                     if isinstance(data, list):
#                         for d in data:
#                             if isinstance(d, dict) and d.get("@type") == "Person":
#                                 name = d.get("name")
#                                 break
#                 if name:
#                     break

#     if not name:
#         with contextlib.suppress(Exception):
#             title = await page.title()
#             if title:
#                 name = title.split(" | ")[0].strip()

#     # Headline
#     headline = None
#     headline_selectors = [
#         "div.text-body-medium.break-words",
#         "[data-view-name='identity-component'] .text-body-medium",
#         ".pv-top-card span[dir='ltr']",
#         ".top-card-layout__headline",
#         ".text-body-medium",
#         "[data-test-id='hero-summary']",
#         ".profile-top-card__headline",
#     ]
#     for selector in headline_selectors:
#         headline = await _safe_text(page.locator(selector).first)
#         if headline:
#             break

#     # Location (collect candidates, pick best)
#     location = None
#     location_selectors = [
#         "section.pv-top-card span.text-body-small",
#         ".pv-text-details__left-panel span.text-body-small",
#         ".top-card-layout__first-subline span",
#         ".text-body-small.inline.t-black--light.break-words",
#         "[data-test-id='hero-location']",
#         ".profile-top-card__location",
#         ".profile-topcard__location-data",
#     ]
#     for selector in location_selectors:
#         candidate = await _safe_text(page.locator(selector).first)
#         if candidate and candidate.strip().lower() not in PRONOUN_TOKENS:
#             location = candidate.strip()
#             break

#     loc_candidates: List[str] = []
#     for sel in [
#         "div.pv-text-details__left-panel span.text-body-small",
#         "[data-view-name='identity-component'] .text-body-small",
#         ".pv-top-card--list-bullet li",
#         "[data-test-id='hero-location']",
#         ".profile-top-card__location",
#         ".profile-topcard__location-data",
#     ]:
#         with contextlib.suppress(Exception):
#             loc_candidates.extend(await _gather_texts(page.locator(sel)))
#     if not location:
#         location = _pick_location(loc_candidates)

#     # Details (right-panel chips - pronouns, etc.)
#     details = await _gather_texts(page.locator("ul.pv-text-details__right-panel"))

#     return {
#         "name": name.strip() if name else None,
#         "headline": headline,
#         "location": location,
#         "details": details or [],
#     }
# # ===== BASIC INFO: extractor (end) =====



# # ===== ABOUT: extractor =====
# # async def extract_about(page: Page) -> Optional[str]:
# #     selectors = [
# #         "section#about",
# #         "[data-view-name='about']",
# #         "section[data-test-id='about']",
# #     ]
# #     section = None
# #     for sel in selectors:
# #         loc = page.locator(sel)
# #         if await loc.count() > 0:
# #             section = loc.first
# #             break
# #     if section is None:
# #         return None

# #     with contextlib.suppress(Exception):
# #         await section.scroll_into_view_if_needed()

# #     # Click "see more" quickly if present
# #     with contextlib.suppress(Exception):
# #         buttons = section.get_by_role("button", name=re.compile(r"(see|show)\s+more", re.I))
# #         for idx in range(await buttons.count()):
# #             btn = buttons.nth(idx)
# #             if await btn.is_visible():
# #                 await btn.click(timeout=1200)

# #     text_selectors = [
# #         ".inline-show-more-text span[aria-hidden='false']",
# #         ".inline-show-more-text span:not([aria-hidden='true'])",
# #         "[data-test-id='text-block'] span[aria-hidden='false']",
# #         "div[data-test-id='text-with-see-more'] span[aria-hidden='false']",
# #         ".pvs-list__outer-container span[aria-hidden='true']",
# #         ".pvs-list__outer-container span:not([aria-hidden='true'])",
# #         "p",
# #     ]
# #     for sel in text_selectors:
# #         txt = await _safe_text(section.locator(sel).first)
# #         if txt:
# #             cleaned = clean_text(txt.replace("About", "", 1))
# #             if cleaned:
# #                 return cleaned

# #     fallback = await _safe_text(section)
# #     if fallback:
# #         cleaned = clean_text(fallback.replace("About", "", 1))
# #         if cleaned:
# #             return cleaned

# #     html = await page.content()
# #     soup = BeautifulSoup(html, "lxml")
# #     about_sec = soup.select_one("section#about, [data-view-name='about'], section[data-test-id='about']")
# #     if about_sec:
# #         rich = about_sec.select_one(".inline-show-more-text span[aria-hidden='false']")
# #         if rich and clean_text(rich.get_text()):
# #             return clean_text(rich.get_text())
# #         txt = clean_text(about_sec.get_text())
# #         if txt:
# #             return clean_text(txt.replace("About", "", 1))
# #     alt = soup.select_one(".pv-about__summary-text, .display-flex .inline-show-more-text")
# #     return clean_text(alt.get_text()) if alt else None





# #           top skills 

# # async def extract_about(page: Page) -> Optional[str]:
# #     """
# #     Robust About extractor:
# #     - Scrolls until the About section mounts
# #     - Expands any 'See more'
# #     - Returns ONLY text from the About section (never the headline)
# #     - Preserves newlines & emojis
# #     """
# #     section_sel = (
# #         "section#about, "
# #         "section[aria-label='About'], "
# #         "section:has(h2:has-text('About'))"
# #     )

# #     # Ensure the About section is actually in the DOM (LinkedIn lazy-loads it)
# #     for _ in range(12):
# #         if await page.locator(section_sel).count() > 0:
# #             break
# #         # small scroll step to trigger virtualization
# #         await page.mouse.wheel(0, 1200)
# #         await asyncio.sleep(0.15)

# #     if await page.locator(section_sel).count() == 0:
# #         return None

# #     section = page.locator(section_sel).first
# #     with contextlib.suppress(Exception):
# #         await section.scroll_into_view_if_needed()

# #     # Expand any 'See more' inside the About section
# #     with contextlib.suppress(Exception):
# #         more = section.locator(
# #             "button:has-text('See more'), "
# #             "button:has-text('Show more'), "
# #             "button.inline-show-more-text__button, "
# #             "button[aria-expanded='false']"
# #         )
# #         for i in range(await more.count()):
# #             btn = more.nth(i)
# #             if await btn.is_visible():
# #                 with contextlib.suppress(Exception):
# #                     await btn.click(timeout=1200)
# #                     await asyncio.sleep(0.1)

# #     # Prefer rich containers, but STRICTLY inside the About section
# #     # Keep line breaks so bullets/paragraphs survive.
# #     js = """(root) => {
# #       const scope = root.querySelector('.inline-show-more-text')
# #                  || root.querySelector('.pv-shared-text-with-see-more')
# #                  || root;
# #       // pull paragraphs, list items, and visible spans
# #       const nodes = scope.querySelectorAll('p, li, span[aria-hidden="false"]');
# #       const lines = [];
# #       nodes.forEach(el => {
# #         const t = (el.innerText || '').replace(/^\\s+|\\s+$/g,'');
# #         if (t) lines.push(t);
# #       });
# #       let out = lines.join('\\n');
# #       out = out.replace(/^\\s*About\\s*\\n?/i, '').trim();
# #       return out || null;
# #     }"""
# #     with contextlib.suppress(Exception):
# #         txt = await section.evaluate(js)
# #         if txt:
# #             return txt

# #     # Fallback: plain innerText of the section (still scoped)
# #     with contextlib.suppress(Exception):
# #         raw = await section.inner_text()
# #         if raw:
# #             raw = re.sub(r"^\\s*About\\s*", "", raw, flags=re.I).strip()
# #             # collapse excessive spaces but keep newlines
# #             raw = re.sub(r"[ \\t]+", " ", raw)
# #             return raw or None

# #     return None


# async def extract_about(page: Page) -> Optional[str]:
#     """
#     Extracts ONLY the actual About text, not the 'Top skills' widget that
#     appears at the bottom of the About section.

#     Strategy:
#     1) Ensure the About section is mounted (LinkedIn lazy-loads).
#     2) Scroll it into view and expand any 'See more'.
#     3) Read section.inner_text() (keeps emojis & line breaks).
#     4) Remove the heading and anything after 'Top skills'.
#     """
#     section_sel = "section#about, section[aria-label='About'], section:has(h2:has-text('About'))"

#     # 1) Ensure the About section exists (lazy-loaded)
#     for _ in range(12):
#         if await page.locator(section_sel).count() > 0:
#             break
#         await page.mouse.wheel(0, 1200)
#         await asyncio.sleep(0.15)

#     if await page.locator(section_sel).count() == 0:
#         return None

#     section = page.locator(section_sel).first
#     with contextlib.suppress(Exception):
#         await section.scroll_into_view_if_needed()

#     # 2) Expand any 'See more' inside the About section
#     with contextlib.suppress(Exception):
#         more = section.locator(
#             "button:has-text('See more'), "
#             "button:has-text('Show more'), "
#             "button.inline-show-more-text__button, "
#             "button[aria-expanded='false']"
#         )
#         for i in range(await more.count()):
#             btn = more.nth(i)
#             if await btn.is_visible():
#                 with contextlib.suppress(Exception):
#                     await btn.click(timeout=1200)
#                     await asyncio.sleep(0.1)

#     # 3) Take the full visible text of the section
#     try:
#         raw = await section.inner_text()
#     except Exception:
#         raw = None
#     if not raw:
#         return None

#     # 4) Clean it: drop heading and anything after "Top skills"
#     import re
#     txt = raw.replace("\r", "")
#     # Remove the 'About' heading if present
#     txt = re.sub(r"^\s*About\s*\n?", "", txt, flags=re.I)
#     # Remove everything from "Top skills" (or similar) to the end
#     txt = re.sub(r"\n\s*Top\s*skills\b[\s\S]*$", "", txt, flags=re.I).strip()
#     # Tidy trailing "See less"/"See more" if leaked
#     txt = re.sub(r"(See\s+(more|less))\s*$", "", txt, flags=re.I).strip()

#     # Normalize: keep meaningful lines, drop empty noise lines
#     lines = [ln.rstrip() for ln in txt.splitlines()]
#     lines = [ln for ln in lines if ln.strip() != ""]
#     cleaned = "\n".join(lines).strip()

#     return cleaned or None



# # ===== ABOUT: extractor (end) =====


# # ------------------------- Other sections (originals) -------------------------

# async def extract_section_list(page: Page, section_id_marker: str) -> List[Dict[str, Any]]:
#     html = await page.content()
#     soup = BeautifulSoup(html, "lxml")
#     sections: List[Dict[str, Any]] = []
#     seen: set[tuple[str, str, str]] = set()

#     def pick_text(node, selectors: List[str]) -> Optional[str]:
#         for selector in selectors:
#             found = node.select_one(selector)
#             if not found:
#                 continue
#             text_val = clean_text(found.get_text())
#             if text_val:
#                 return text_val
#         return None

#     def register_entry(title: Optional[str], subtitle: Optional[str], date: Optional[str], raw: Optional[str]) -> None:
#         if not raw:
#             return
#         key = (
#             (title or '').lower(),
#             (subtitle or '').lower(),
#             (date or '').lower(),
#         )
#         if not any(key):
#             return
#         if key in seen:
#             return
#         seen.add(key)
#         sections.append({
#             'title': title,
#             'subtitle': subtitle,
#             'date': date,
#             'raw_html': raw,
#         })

#     def parse_item(node) -> None:
#         if not node:
#             return
#         title = pick_text(node, [
#             ".mr1.hoverable-link-text span[aria-hidden='true']",
#             ".mr1.hoverable-link-text.t-bold span[aria-hidden='true']",
#             ".mr1.hoverable-link-text span",
#             ".t-bold span[aria-hidden='true']",
#             ".t-bold[aria-hidden='true']",
#             ".t-bold",
#             "h3",
#             "h4",
#         ])
#         subtitle = pick_text(node, [
#             ".t-14.t-normal span[aria-hidden='true']",
#             ".t-14.t-normal",
#             ".pvs-entity__path-node span.t-14",
#             ".pv-entity__secondary-title",
#             ".pvs-entity__subtitle",
#             "h4.t-14",
#             "p",
#         ])
#         date = pick_text(node, [
#             "span.t-14.t-normal.t-black--light span[aria-hidden='true']",
#             "span.t-14.t-normal.t-black--light",
#             ".pv-entity__date-range span:nth-of-type(2)",
#             "time",
#         ])
#         raw = clean_text(node.get_text())
#         register_entry(title, subtitle, date, raw)

#         for nested_list in node.select("ul, ol"):
#             for nested_item in nested_list.find_all('li', recursive=False):
#                 parse_item(nested_item)

#     heading = soup.find(lambda tag: tag.name in ['h2', 'h3'] and section_id_marker.lower() in tag.get_text().lower())
#     section = heading.find_parent('section') if heading else None
#     if not section:
#         section = soup.select_one(f"section[id*='{section_id_marker}'], section[aria-label*='{section_id_marker}']")
#     if not section:
#         return sections

#     candidates = section.select('li.pvs-list__item, li.pvs-list__item--line-separated, li.artdeco-list__item')
#     if not candidates:
#         candidates = section.find_all('li')

#     for node in candidates:
#         parse_item(node)

#     return sections

# async def extract_skills(page: Page) -> List[str]:
#     html = await page.content()
#     soup = BeautifulSoup(html, "lxml")
#     skills: List[str] = []
#     for s in soup.select(".pv-skill-category-entity__name, .skill-pill, .pv-skill-category-entity__skill"):
#         txt = clean_text(s.get_text())
#         if txt:
#             skills.append(txt)
#     if not skills:
#         for s in soup.select(".skill"):
#             txt = clean_text(s.get_text())
#             if txt:
#                 skills.append(txt)
#     return list(dict.fromkeys(skills))

# async def extract_posts(page: Page, max_posts=50) -> List[Dict[str, Any]]:
#     if max_posts <= 0:
#         return []

#     posts: List[Dict[str, Any]] = []
#     try:
#         loc = page.url.rstrip("/")
#         activity_url = loc + "/detail/recent-activity/shares/"
#         await page.goto(activity_url, wait_until="domcontentloaded")
#         # Wait briefly for any post container; don't block long
#         with contextlib.suppress(Exception):
#             await page.wait_for_selector(
#                 "div.occludable-update, div.feed-shared-update-v2, article.feed-shared-update, div.feed-shared-update",
#                 timeout=2500
#             )
#     except Exception:
#         pass

#     # Choose minimal scroll passes based on requested max_posts
#     # (LinkedIn shows ~4–8 per fold; we aim low and stop early when enough are loaded)
#     est_per_fold = 6
#     needed_folds = max(1, min(12, (max_posts + est_per_fold - 1) // est_per_fold))
#     scroll_passes = min(12, needed_folds)

#     await scroll_to_load(
#         page,
#         scroll_runs=scroll_passes,
#         wait_between=SCROLL_WAIT_BETWEEN,
#         stop_when_selector="div.occludable-update, div.feed-shared-update-v2, article.feed-shared-update, div.feed-shared-update",
#         stop_count=max_posts
#     )

#     html = await page.content()
#     soup = BeautifulSoup(html, "lxml")

#     post_selectors = soup.select("div.occludable-update, div.feed-shared-update-v2, article.feed-shared-update")
#     if not post_selectors:
#         post_selectors = soup.select("div.feed-shared-update")

#     for p in post_selectors:
#         if len(posts) >= max_posts:
#             break
#         try:
#             text_el = p.select_one(".feed-shared-update-v2__description, .feed-shared-text, .update-components-text")
#             text = clean_text(text_el.get_text()) if text_el else clean_text(p.get_text())
#             date_el = p.select_one("span.feed-shared-actor__meta, span.feed-shared-actor__sub-description, time")
#             date = clean_text(date_el.get_text()) if date_el else None
#             react_el = p.select_one(".social-details-social-counts__reactions-count, .social-details-social-counts__reactions, button[data-control-name='likes_count']")
#             reactions = clean_text(react_el.get_text()) if react_el else None
#             comm_el = p.select_one(".social-details-social-counts__comments, button[data-control-name='comments_count']")
#             comments = clean_text(comm_el.get_text()) if comm_el else None

#             medias = []
#             for img in p.select("img"):
#                 src = img.get("src")
#                 if src and "profile" not in src and len(src) > 10:
#                     medias.append(src)

#             posts.append({
#                 "text": text,
#                 "date": date,
#                 "reactions": reactions,
#                 "comments_count": comments,
#                 "media": list(dict.fromkeys(medias)),
#                 "raw_html_snippet": clean_text(str(p)[:2000])
#             })
#         except Exception:
#             continue

#     # Deduplicate by (text, date, media)
#     deduped_posts: List[Dict[str, Any]] = []
#     seen_posts: set[tuple[str, Optional[str], tuple[str, ...]]] = set()
#     for post in posts:
#         text_val = post.get('text')
#         if not text_val:
#             continue
#         key = (
#             text_val,
#             post.get('date'),
#             tuple(post.get('media') or ()),
#         )
#         if key in seen_posts:
#             continue
#         seen_posts.add(key)
#         deduped_posts.append(post)

#     return deduped_posts

# # ------------------------- Main -------------------------

# async def scrape_profile(url: str, storage_state: str, max_posts: int = 50, headful: bool = False) -> Dict[str, Any]:
#     async with async_playwright() as p:
#         browser = await p.chromium.launch(headless=not headful)
#         context = await browser.new_context(storage_state=storage_state)

#         # Apply faster defaults
#         context.set_default_timeout(ACTION_TIMEOUT_MS)
#         page = await context.new_page()
#         page.set_default_timeout(ACTION_TIMEOUT_MS)
#         page.set_default_navigation_timeout(NAV_TIMEOUT_MS)

#         await page.goto(url, wait_until="domcontentloaded")
#         with contextlib.suppress(Exception):
#             await page.wait_for_selector("main", timeout=3500)
#         with contextlib.suppress(Exception):
#             await page.wait_for_selector("main h1, h1.text-heading-xlarge", timeout=3500)

#         preload_scrolls = 2 if max_posts > 0 else 1
#         await scroll_to_load(page, scroll_runs=preload_scrolls, wait_between=SCROLL_WAIT_BETWEEN)
#         with contextlib.suppress(Exception):
#             await page.evaluate("window.scrollTo(0, 0)")

#         if "login" in page.url and "linkedin.com" in page.url:
#             raise RuntimeError("Looks like LinkedIn requires login. Ensure your storage state is valid and logged-in.")

#         canonical_url: Optional[str] = None
#         with contextlib.suppress(Exception):
#             canonical_url = await page.eval_on_selector("link[rel='canonical']", "el => el.href")
#         profile_url = (canonical_url or page.url or url).split("?")[0]

#         basic = await _scrape_basic_profile(page)
#         await scroll_to_load(
#     page,
#     scroll_runs=4,  # small bump so About reliably appears
#     wait_between=SCROLL_WAIT_BETWEEN,
#     stop_when_selector="section#about, section[aria-label='About'], section:has(h2:has-text('About'))",
#     stop_count=1
# )

#         about = await extract_about(page)

#         profile: Dict[str, Any] = {
#             "input_url": url,
#             "profile_url": profile_url,
#             "name": basic.get("name"),
#             "headline": basic.get("headline"),
#             "location": basic.get("location"),
#             "details": basic.get("details"),
#             "about": about,
#         }

#         profile["experience"] = await extract_section_list(page, "experience")
#         profile["education"] = await extract_section_list(page, "education")
#         profile["skills"] = await extract_skills(page)

#         try:
#             posts = await extract_posts(page, max_posts=max_posts)
#         except Exception:
#             posts = []
#         profile["posts"] = posts

#         recent_activity_url = page.url
#         if recent_activity_url and recent_activity_url != profile_url:
#             profile["recent_activity_url"] = recent_activity_url
#         profile["scraped_url"] = profile_url
#         profile["scrape_timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")

#         await browser.close()
#         return profile

# def parse_args():
#     p = argparse.ArgumentParser()
#     p.add_argument("--url", required=True, help="LinkedIn profile URL")
#     p.add_argument("--storage", required=True, help="Playwright storage_state.json path (logged-in state)")
#     p.add_argument("--max-posts", type=int, default=50)
#     p.add_argument("--output", default="linkedin_profile.json")
#     p.add_argument("--headful", action="store_true", help="Run with headed browser (useful for debugging)")
#     return p.parse_args()

# if __name__ == "__main__":
#     args = parse_args()
#     data = asyncio.run(scrape_profile(args.url, args.storage, max_posts=args.max_posts, headful=args.headful))
#     with open(args.output, "w", encoding="utf-8") as f:
#         json.dump(data, f, indent=2, ensure_ascii=False)
#     print("Saved to", args.output)
#     print(json.dumps({k: data.get(k) for k in ("name", "headline", "about")}, indent=2, ensure_ascii=False))






import argparse
import asyncio
import contextlib
import json
import re
import time
from typing import List, Dict, Any, Optional

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page




# --- add this function wrapper ---
def run_profile_scrape(profile_url: str) -> dict:
    """
    Return a Python dict with the scraped data for a given profile_url.
    Keep your existing code but make sure to return a dict at the end.
    """
    # TODO: call your existing scraping code here
    # Example: data = scrape_profile(profile_url)
    data = {"profile_url": profile_url, "ok": True}  # replace with real result
    return data

if __name__ == "__main__":
    # optional: accept argv for standalone runs
    import sys, json
    url = sys.argv[1]
    print(json.dumps(run_profile_scrape(url)))







# ------------------------- Faster defaults -------------------------

NAV_TIMEOUT_MS = 9000        # navigation timeouts
ACTION_TIMEOUT_MS = 3500     # locator waits, clicks, selectors
SCROLL_WAIT_BETWEEN = 0.25   # seconds between scrolls

# ------------------------- Utils -------------------------

def clean_text(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    # keep newlines but normalize whitespace around them
    s = s.replace("\r", "")
    lines = [ln.strip() for ln in s.split("\n")]
    # collapse multi-blank lines to single
    out_lines = []
    for ln in lines:
        if ln == "" and (len(out_lines) == 0 or out_lines[-1] == ""):
            continue
        out_lines.append(ln)
    return "\n".join(out_lines).strip()

async def scroll_to_load(
    page: Page,
    scroll_runs: int = 10,
    wait_between: float = SCROLL_WAIT_BETWEEN,
    stop_when_selector: Optional[str] = None,
    stop_count: Optional[int] = None,
):
    """
    Fast, adaptive scroller:
    - shorter waits
    - stops when page height stops growing
    - optional early stop when enough items are on the page
    """
    prev_height = None
    stagnant = 0
    for _ in range(scroll_runs):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(wait_between)

        # Early stop: enough items?
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

# Helpers commonly used across extractors
async def _gather_texts(locator) -> List[str]:
    texts: List[str] = []
    with contextlib.suppress(Exception):
        raw_texts = await locator.all_inner_texts()
        for raw in raw_texts:
            for chunk in raw.splitlines():
                value = chunk.strip()
                if value:
                    texts.append(value)
    # de-dupe preserving order
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

# ------------------------- BASIC INFO + ABOUT -------------------------

PRONOUN_TOKENS = {
    "he/him", "she/her", "they/them", "he • him", "she • her", "they • them"
}

def _pick_location(candidates: List[str]) -> Optional[str]:
    """Choose the most location-like string (skip pronouns)."""
    for c in candidates:
        t = (c or "").strip()
        if not t:
            continue
        tl = t.lower()
        if tl in PRONOUN_TOKENS:
            continue
        if ("," in t) or any(k in tl for k in [
            "india","united","usa","uk","uae","germany","canada","australia",
            "hyderabad","bengaluru","mumbai","delhi","pune","chennai",
            "gurgaon","noida","kolkata","ahmedabad","coimbatore",
            "trivandrum","vizag","mysuru","texas","united states"
        ]):
            return t
    for t in candidates:
        tl = (t or "").lower().strip()
        if tl and tl not in PRONOUN_TOKENS:
            return t
    return None

# ===== BASIC INFO: extractor =====
async def _scrape_basic_profile(page: Page) -> Dict[str, Any]:
    # Name
    name = None
    name_selectors = [
        "section.pv-top-card h1",
        "[data-view-name='identity-component'] h1",
        "main h1",
        "main h1.text-heading-xlarge",
        ".top-card-layout__entity-info h1",
        ".top-card-layout__title",
        ".text-heading-xlarge",
        "[data-test-id='hero-title']",
        "[data-test-id='profile-card-full-name']",
        ".profile-top-card__name",
    ]
    for selector in name_selectors:
        name = await _safe_text(page.locator(selector).first)
        if name:
            break

    if not name:
        with contextlib.suppress(Exception):
            ld_jsons = await page.eval_on_selector_all(
                "script[type='application/ld+json']",
                "els => els.map(e => e.textContent)"
            )
            for raw in ld_jsons:
                with contextlib.suppress(Exception):
                    data = json.loads(raw)
                    if isinstance(data, dict) and data.get("@type") == "Person":
                        name = data.get("name")
                        break
                    if isinstance(data, list):
                        for d in data:
                            if isinstance(d, dict) and d.get("@type") == "Person":
                                name = d.get("name")
                                break

    if not name:
        with contextlib.suppress(Exception):
            title = await page.title()
            if title:
                name = title.split(" | ")[0].strip()

    # Headline
    headline = None
    headline_selectors = [
        "div.text-body-medium.break-words",
        "[data-view-name='identity-component'] .text-body-medium",
        ".pv-top-card span[dir='ltr']",
        ".top-card-layout__headline",
        ".text-body-medium",
        "[data-test-id='hero-summary']",
        ".profile-top-card__headline",
    ]
    for selector in headline_selectors:
        headline = await _safe_text(page.locator(selector).first)
        if headline:
            break

    # Location
    location = None
    location_selectors = [
        "section.pv-top-card span.text-body-small",
        ".pv-text-details__left-panel span.text-body-small",
        ".top-card-layout__first-subline span",
        ".text-body-small.inline.t-black--light.break-words",
        "[data-test-id='hero-location']",
        ".profile-top-card__location",
        ".profile-topcard__location-data",
    ]
    for selector in location_selectors:
        candidate = await _safe_text(page.locator(selector).first)
        if candidate and candidate.strip().lower() not in PRONOUN_TOKENS:
            location = candidate.strip()
            break

    loc_candidates: List[str] = []
    for sel in [
        "div.pv-text-details__left-panel span.text-body-small",
        "[data-view-name='identity-component'] .text-body-small",
        ".pv-top-card--list-bullet li",
        "[data-test-id='hero-location']",
        ".profile-top-card__location",
        ".profile-topcard__location-data",
    ]:
        with contextlib.suppress(Exception):
            loc_candidates.extend(await _gather_texts(page.locator(sel)))
    if not location:
        location = _pick_location(loc_candidates)

    # Details (right-panel chips)
    details = await _gather_texts(page.locator("ul.pv-text-details__right-panel"))

    return {
        "name": name.strip() if name else None,
        "headline": headline,
        "location": location,
        "details": details or [],
    }

# ===== ABOUT: extractor (robust; avoids 'Top skills') =====
async def extract_about(page: Page) -> Optional[str]:
    """
    Extracts ONLY the actual About text, not the 'Top skills' widget at the bottom.
    Steps:
    1) Ensure About section mounts (LinkedIn lazy-loads).
    2) Expand any 'See more'.
    3) Read section.inner_text() and strip 'About' heading + anything after 'Top skills'.
    """
    section_sel = "section#about, section[aria-label='About'], section:has(h2:has-text('About'))"

    # Ensure About section exists
    for _ in range(12):
        if await page.locator(section_sel).count() > 0:
            break
        await page.mouse.wheel(0, 1200)
        await asyncio.sleep(0.15)

    if await page.locator(section_sel).count() == 0:
        return None

    section = page.locator(section_sel).first
    with contextlib.suppress(Exception):
        await section.scroll_into_view_if_needed()

    # Expand 'See more' inside the About section
    with contextlib.suppress(Exception):
        more = section.locator(
            "button:has-text('See more'), "
            "button:has-text('Show more'), "
            "button.inline-show-more-text__button, "
            "button[aria-expanded='false']"
        )
        for i in range(await more.count()):
            btn = more.nth(i)
            if await btn.is_visible():
                with contextlib.suppress(Exception):
                    await btn.click(timeout=1200)
                    await asyncio.sleep(0.1)

    # Pull the full visible text of the section
    try:
        raw = await section.inner_text()
    except Exception:
        raw = None
    if not raw:
        return None

    txt = raw.replace("\r", "")
    # Remove the 'About' heading if present
    txt = re.sub(r"^\s*About\s*\n?", "", txt, flags=re.I)
    # Remove everything from "Top skills" (or similar) to the end
    txt = re.sub(r"\n\s*Top\s*skills\b[\s\S]*$", "", txt, flags=re.I).strip()
    # Trim trailing 'See more/less' if leaked
    txt = re.sub(r"(See\s+(more|less))\s*$", "", txt, flags=re.I).strip()

    cleaned = clean_text(txt)
    return cleaned or None

# ------------------------- Other sections (optional) -------------------------

async def extract_section_list(page: Page, section_id_marker: str) -> List[Dict[str, Any]]:
    html = await page.content()
    soup = BeautifulSoup(html, "lxml")
    sections: List[Dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def pick_text(node, selectors: List[str]) -> Optional[str]:
        for selector in selectors:
            found = node.select_one(selector)
            if not found:
                continue
            text_val = clean_text(found.get_text())
            if text_val:
                return text_val
        return None

    def register_entry(title: Optional[str], subtitle: Optional[str], date: Optional[str], raw: Optional[str]) -> None:
        if not raw:
            return
        key = (
            (title or '').lower(),
            (subtitle or '').lower(),
            (date or '').lower(),
        )
        if not any(key):
            return
        if key in seen:
            return
        seen.add(key)
        sections.append({
            'title': title,
            'subtitle': subtitle,
            'date': date,
            'raw_html': raw,
        })

    def parse_item(node) -> None:
        if not node:
            return
        title = pick_text(node, [
            ".mr1.hoverable-link-text span[aria-hidden='true']",
            ".mr1.hoverable-link-text.t-bold span[aria-hidden='true']",
            ".mr1.hoverable-link-text span",
            ".t-bold span[aria-hidden='true']",
            ".t-bold[aria-hidden='true']",
            ".t-bold",
            "h3",
            "h4",
        ])
        subtitle = pick_text(node, [
            ".t-14.t-normal span[aria-hidden='true']",
            ".t-14.t-normal",
            ".pvs-entity__path-node span.t-14",
            ".pv-entity__secondary-title",
            ".pvs-entity__subtitle",
            "h4.t-14",
            "p",
        ])
        date = pick_text(node, [
            "span.t-14.t-normal.t-black--light span[aria-hidden='true']",
            "span.t-14.t-normal.t-black--light",
            ".pv-entity__date-range span:nth-of-type(2)",
            "time",
        ])
        raw = clean_text(node.get_text())
        register_entry(title, subtitle, date, raw)

        for nested_list in node.select("ul, ol"):
            for nested_item in nested_list.find_all('li', recursive=False):
                parse_item(nested_item)

    heading = soup.find(lambda tag: tag.name in ['h2', 'h3'] and section_id_marker.lower() in tag.get_text().lower())
    section = heading.find_parent('section') if heading else None
    if not section:
        section = soup.select_one(f"section[id*='{section_id_marker}'], section[aria-label*='{section_id_marker}']")
    if not section:
        return sections

    candidates = section.select('li.pvs-list__item, li.pvs-list__item--line-separated, li.artdeco-list__item')
    if not candidates:
        candidates = section.find_all('li')

    for node in candidates:
        parse_item(node)

    return sections

async def extract_skills(page: Page) -> List[str]:
    html = await page.content()
    soup = BeautifulSoup(html, "lxml")
    skills: List[str] = []
    for s in soup.select(".pv-skill-category-entity__name, .skill-pill, .pv-skill-category-entity__skill"):
        txt = clean_text(s.get_text())
        if txt:
            skills.append(txt)
    if not skills:
        for s in soup.select(".skill"):
            txt = clean_text(s.get_text())
            if txt:
                skills.append(txt)
    return list(dict.fromkeys(skills))

# ------------------------- Posts (ALL available) -------------------------

def _post_key(post: Dict[str, Any]) -> tuple:
    return (
        post.get("text") or "",
        post.get("date") or "",
        tuple(post.get("media") or ()),
    )

async def extract_posts(page: Page, max_posts: int = -1) -> List[Dict[str, Any]]:
    """
    Extract recent posts from /detail/recent-activity/shares/.
    If max_posts < 0, keeps scrolling until no new posts appear (ALL available).
    """
    loc = page.url.rstrip("/")
    activity_url = loc + "/detail/recent-activity/shares/"
    with contextlib.suppress(Exception):
        await page.goto(activity_url, wait_until="domcontentloaded")
        await page.wait_for_selector(
            "div.occludable-update, div.feed-shared-update-v2, article.feed-shared-update, div.feed-shared-update",
            timeout=2500
        )

    posts: List[Dict[str, Any]] = []
    seen_keys: set = set()

    # scroll loop: stop when no new posts after several passes
    stagnant = 0
    last_len = 0
    max_scroll_cycles = 120  # safety cap

    for _ in range(max_scroll_cycles):
        # one small scroll step
        await scroll_to_load(
            page,
            scroll_runs=1,
            wait_between=SCROLL_WAIT_BETWEEN,
            stop_when_selector=None,
            stop_count=None
        )

        html = await page.content()
        soup = BeautifulSoup(html, "lxml")

        post_nodes = soup.select("div.occludable-update, div.feed-shared-update-v2, article.feed-shared-update")
        if not post_nodes:
            post_nodes = soup.select("div.feed-shared-update")

        for p in post_nodes:
            text_el = p.select_one(".feed-shared-update-v2__description, .feed-shared-text, .update-components-text")
            text = clean_text(text_el.get_text()) if text_el else clean_text(p.get_text())
            # cheap filter to avoid grabbing the entire page chrome
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
            if key not in seen_keys and (post.get("text") or "").strip():
                seen_keys.add(key)
                posts.append(post)

        if max_posts > 0 and len(posts) >= max_posts:
            posts = posts[:max_posts]
            break

        if len(posts) == last_len:
            stagnant += 1
        else:
            stagnant = 0
        last_len = len(posts)

        # if asking "all", stop when no new posts after a few scrolls
        if max_posts < 0 and stagnant >= 6:
            break

    return posts

# ------------------------- Main -------------------------

async def scrape_profile(url: str, storage_state: str, max_posts: int = -1, headful: bool = False, block_media: bool = False) -> Dict[str, Any]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not headful)
        context = await browser.new_context(storage_state=storage_state)
        context.set_default_timeout(ACTION_TIMEOUT_MS)
        page = await context.new_page()
        page.set_default_timeout(ACTION_TIMEOUT_MS)
        page.set_default_navigation_timeout(NAV_TIMEOUT_MS)

        if block_media:
            await context.route("**/*", lambda route: route.abort() if route.request.resource_type in {"image","media","font"} else route.continue_())

        await page.goto(url, wait_until="domcontentloaded")
        with contextlib.suppress(Exception):
            await page.wait_for_selector("main", timeout=3500)
        with contextlib.suppress(Exception):
            await page.wait_for_selector("main h1, h1.text-heading-xlarge", timeout=3500)

        # small pre-scroll so About mounts
        await scroll_to_load(
            page,
            scroll_runs=4,
            wait_between=SCROLL_WAIT_BETWEEN,
            stop_when_selector="section#about, section[aria-label='About'], section:has(h2:has-text('About'))",
            stop_count=1
        )
        with contextlib.suppress(Exception):
            await page.evaluate("window.scrollTo(0, 0)")

        if "login" in page.url and "linkedin.com" in page.url:
            raise RuntimeError("LinkedIn requires login. Ensure your storage_state is valid and logged-in.")

        canonical_url: Optional[str] = None
        with contextlib.suppress(Exception):
            canonical_url = await page.eval_on_selector("link[rel='canonical']", "el => el.href")
        profile_url = (canonical_url or page.url or url).split("?")[0]

        basic = await _scrape_basic_profile(page)
        about = await extract_about(page)

        profile: Dict[str, Any] = {
            "input_url": url,
            "profile_url": profile_url,
            "name": basic.get("name"),
            "headline": basic.get("headline"),
            "location": basic.get("location"),
            "details": basic.get("details"),
            "about": about,
        }

        # Optional: keep these if you also want them in the output
        profile["experience"] = await extract_section_list(page, "experience")
        profile["education"] = await extract_section_list(page, "education")
        profile["skills"] = await extract_skills(page)

        try:
            posts = await extract_posts(page, max_posts=max_posts)
        except Exception:
            posts = []
        profile["posts"] = posts

        profile["scraped_url"] = profile_url
        profile["scrape_timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")

        await browser.close()
        return profile

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True, help="LinkedIn profile URL")
    p.add_argument("--storage", required=True, help="Playwright storage_state.json path (logged-in state)")
    p.add_argument("--all-posts", action="store_true", help="Fetch ALL available posts (keep scrolling until no more)")
    p.add_argument("--max-posts", type=int, default=50, help="If provided, cap number of posts; ignored if --all-posts")
    p.add_argument("--output", default="linkedin_profile.json")
    p.add_argument("--headful", action="store_true", help="Run with headed browser (for debugging)")
    p.add_argument("--block-media", action="store_true", help="Block images/media/fonts (faster; post images missing)")
    return p.parse_args()

if __name__ == "__main__":
    args = parse_args()
    max_posts = -1 if args.all_posts else args.max_posts
    data = asyncio.run(
        scrape_profile(
            args.url,
            args.storage,
            max_posts=max_posts,
            headful=args.headful,
            block_media=args.block_media
        )
    )
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("Saved to", args.output)
    print(json.dumps({k: data.get(k) for k in ("name", "headline", "about")}, indent=2, ensure_ascii=False))



# working great with all the posts and about section 
# python scrape.py --url "https://www.linkedin.com/in/sravya-anne/" --storage storage_state.json --output outv3.json 