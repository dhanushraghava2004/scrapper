# python Linkedin.py "https://www.linkedin.com/in/dhanush-raghava-a995ba307/" --storage storage_state.json --max-posts 50 --output outv1.json




import argparse
import asyncio
import json
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo  # Python 3.9+

from typing import Any, Dict, List, Optional, Set

from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
    BrowserContext,
    Locator,
    Page,
    async_playwright,
)



SECTION_TITLES = {
    "experience": "Experience",
    "education": "Education",
    "skills": "Skills",
    "certifications": "Licenses & certifications",
    "volunteering": "Volunteer experience",
    "honors": "Honors & awards",
    "projects": "Projects",
    "courses": "Courses",
    "publications": "Publications",
    "recommendations": "Recommendations",
    "languages": "Languages",
    "organizations": "Organizations",
    "patents": "Patents",
}




def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen: Set[str] = set()
    result: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


async def _gather_texts(locator: Locator) -> List[str]:
    texts: List[str] = []
    with suppress(Exception):
        raw_texts = await locator.all_inner_texts()
        for raw in raw_texts:
            for chunk in raw.splitlines():
                value = chunk.strip()
                if value:
                    texts.append(value)
    return _dedupe_preserve_order(texts)


async def _safe_text(locator: Locator) -> Optional[str]:
    with suppress(Exception):
        text = await locator.inner_text()
        text = text.strip()
        if text:
            return text
    return None


async def _safe_attribute(locator: Locator, attribute: str) -> Optional[str]:
    with suppress(Exception):
        value = await locator.get_attribute(attribute)
        if value:
            return value.strip()
    return None


async def _collect_links(locator: Locator) -> List[str]:
    anchors = locator.locator("a[href]")
    hrefs: List[str] = []
    count = await anchors.count()
    for index in range(count):
        href = await _safe_attribute(anchors.nth(index), "href")
        if href:
            hrefs.append(href)
    return _dedupe_preserve_order(hrefs)


async def _click_until_stable(root: Any, selectors: List[str], max_rounds: int = 6) -> None:
    for _ in range(max_rounds):
        clicked = False
        for selector in selectors:
            buttons = root.locator(selector)
            count = await buttons.count()
            for index in range(count):
                button = buttons.nth(index)
                try:
                    if not await button.is_visible():
                        continue
                    await button.scroll_into_view_if_needed()
                    await button.click()
                    await button.page.wait_for_timeout(350)
                    clicked = True
                except PlaywrightTimeoutError:
                    continue
                except Exception:
                    continue
        if not clicked:
            break


async def _auto_scroll(page: Page, max_runs: int = 12, delay_ms: int = 750) -> None:
    last_height = -1
    for _ in range(max_runs):
        height = await page.evaluate("() => document.body.scrollHeight")
        if height == last_height:
            break
        await page.evaluate("value => window.scrollTo(0, value)", height)
        await page.wait_for_timeout(delay_ms)
        last_height = height


async def _scrape_basic_profile(page: Page) -> Dict[str, Any]:
    headline = await _safe_text(page.locator("div.text-body-medium.break-words"))
    if not headline:
        headline = await _safe_text(page.locator("div.text-body-medium"))
    location = await _safe_text(page.locator("div.pv-text-details__left-panel span.text-body-small").first)
    if not location:
        location = await _safe_text(page.locator("span.text-body-small").first)
    details = await _gather_texts(page.locator("ul.pv-text-details__right-panel"))
    return {
        "name": await _safe_text(page.locator("h1")),
        "headline": headline,
        "location": location,
        "details": details,
    }


async def _scrape_about(page: Page) -> Optional[str]:
    section = page.locator("section:has(h2:has-text('About'))")
    if await section.count() == 0:
        return None
    target = section.first
    await target.scroll_into_view_if_needed()
    await page.wait_for_timeout(250)
    await _click_until_stable(target, ["button:has-text('See more')"])
    paragraphs = await _gather_texts(target.locator(".inline-show-more-text, .pv-shared-text-with-see-more"))
    if paragraphs:
        return "\n".join(paragraphs)
    return None


async def _scrape_structured_section(page: Page, heading: str) -> List[Dict[str, Any]]:
    section = page.locator(f"section:has(h2:has-text('{heading}'))")
    if await section.count() == 0:
        return []
    target = section.first
    await target.scroll_into_view_if_needed()
    await page.wait_for_timeout(300)
    await _click_until_stable(
        target,
        ["button:has-text('See more')", "button:has-text('Show all')", "button:has-text('Show more')"],
    )
    cards = target.locator(":scope .pvs-list__item")
    if await cards.count() == 0:
        cards = target.locator(":scope li")
    results: List[Dict[str, Any]] = []
    count = await cards.count()
    for index in range(count):
        card = cards.nth(index)
        lines = await _gather_texts(
            card.locator(":scope span[aria-hidden='true'], :scope .t-14, :scope .inline-show-more-text")
        )
        metadata = await _gather_texts(card.locator(":scope .t-12"))
        description = await _safe_text(card.locator(":scope .inline-show-more-text"))
        links = await _collect_links(card)
        payload: Dict[str, Any] = {"order": index}
        if lines:
            payload["lines"] = lines
        if metadata:
            payload["metadata"] = metadata
        if description and (not lines or description not in lines):
            payload["description"] = description
        if links:
            payload["links"] = links
        if payload != {"order": index}:
            results.append(payload)
    if not results:
        raw_text = await _gather_texts(target)
        if raw_text:
            results.append({"order": 0, "lines": raw_text})
    return results


async def _scrape_contact_info(page: Page) -> Dict[str, Any]:
    trigger = page.locator("a:has-text('Contact info'), button:has-text('Contact info')")
    if await trigger.count() == 0:
        return {}
    button = trigger.first
    try:
        await button.scroll_into_view_if_needed()
        await button.click()
        modal = page.locator("div.artdeco-modal")
        await modal.wait_for(state="visible", timeout=5000)
        overlay = modal.first
        sections = overlay.locator("section")
        contact: Dict[str, Any] = {}
        section_count = await sections.count()
        for index in range(section_count):
            block = sections.nth(index)
            title = await _safe_text(block.locator("h3"))
            lines = await _gather_texts(block)
            links = await _collect_links(block)
            key = title.lower().replace(" ", "_") if title else f"section_{index}"
            entry: Dict[str, Any] = {}
            if lines:
                entry["lines"] = lines
            if links:
                entry["links"] = links
            if entry:
                contact[key] = entry
        close_button = overlay.locator("button[aria-label='Dismiss'], button[aria-label='Close']")
        with suppress(Exception):
            await close_button.first.click()
        if not contact:
            raw_modal = await _gather_texts(overlay)
            if raw_modal:
                contact["raw"] = raw_modal
        return contact
    except PlaywrightTimeoutError:
        return {}
    except Exception:
        with suppress(Exception):
            await page.keyboard.press("Escape")
        return {}


async def _scrape_recent_activity(
    context: BrowserContext,
    profile_url: str,
    max_posts: int = 10,
    scroll_runs: int = 8,
) -> List[Dict[str, Any]]:
    if max_posts <= 0:
        return []
    activity_url = profile_url.rstrip("/") + "/recent-activity/all/"
    page = await context.new_page()
    page.set_default_timeout(30000)
    posts: List[Dict[str, Any]] = []
    try:
        await page.goto(activity_url, timeout=60000)
        await page.wait_for_load_state("domcontentloaded")
        await _auto_scroll(page, max_runs=scroll_runs)
        await _click_until_stable(page, ["button:has-text('Show more')", "button:has-text('See more')"])
        cards = page.locator("div.feed-shared-update-v2, div[data-urn^='urn:li:activity'], article")
        total = await cards.count()
        limit = min(total, max_posts)
        for index in range(limit):
            card = cards.nth(index)
            headline = await _safe_text(card.locator(":scope .update-components-actor__title"))
            timestamp = await _safe_text(card.locator(":scope time"))
            content_lines = await _gather_texts(
                card.locator(":scope span[aria-hidden='true'], :scope .feed-shared-text__text-view, :scope .update-components-text")
            )
            counts = await _gather_texts(
                card.locator(
                    ":scope .social-details-social-counts__reactions-count, "
                    ":scope .social-details-social-counts__comments-count, "
                    ":scope .social-details-social-counts__social-proof-text"
                )
            )
            permalink = await _safe_attribute(
                card.locator("a[data-control-name='update_card_permalink']").first,
                "href",
            )
            media_links = await _collect_links(
                card.locator(
                    ":scope .update-components-article, "
                    ":scope .update-components-image, "
                    ":scope .update-components-link, "
                    ":scope .update-components-video"
                )
            )
            entry: Dict[str, Any] = {"order": index}
            if headline:
                entry["heading"] = headline
            if timestamp:
                entry["timestamp"] = timestamp
            if content_lines:
                entry["content"] = content_lines
            if counts:
                entry["social_counts"] = counts
            if permalink:
                entry["permalink"] = permalink
            if media_links:
                entry["media_links"] = media_links
            if entry != {"order": index}:
                posts.append(entry)
        return posts
    except PlaywrightTimeoutError:
        return posts
    except Exception:
        return posts
    finally:
        await page.close()


async def scrape_linkedin_profile(
    url: str,
    *,
    storage_state: str = "linkedin_state.json",
    headless: bool = True,
    max_posts: int = 10,
    scroll_runs: int = 12,
) -> Dict[str, Any]:
    """Scrape a LinkedIn profile using a stored authenticated session state."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        context = await browser.new_context(storage_state=storage_state)
        try:
            page = await context.new_page()
            page.set_default_timeout(30000)
            await page.goto(url, timeout=60000)
            await page.wait_for_load_state("domcontentloaded")
            await _auto_scroll(page, max_runs=scroll_runs)
            await _click_until_stable(
                page,
                ["button:has-text('Show all')", "button:has-text('See more')", "button:has-text('Show more')"],
            )
            await _auto_scroll(page, max_runs=max(1, scroll_runs // 2))
            profile: Dict[str, Any] = {
                "url": url,
                "retrieved_at": datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(timespec="seconds"),
                "basic": await _scrape_basic_profile(page),
                "about": await _scrape_about(page),
                "contact": await _scrape_contact_info(page),
                "sections": {},
                "recent_activity": [],
            }
            sections: Dict[str, Any] = {}
            for key, label in SECTION_TITLES.items():
                items = await _scrape_structured_section(page, label)
                if items:
                    sections[key] = items
            profile["sections"] = sections
            profile["recent_activity"] = await _scrape_recent_activity(
                context,
                url,
                max_posts=max_posts,
                scroll_runs=max(2, scroll_runs // 2),
            )
            return profile
        finally:
            await browser.close()


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scrape LinkedIn profile sections using Playwright and saved cookies.",
    )
    parser.add_argument("url", help="LinkedIn profile URL to scrape.")
    parser.add_argument(
        "--storage-state",
        default="linkedin_state.json",
        help="Path to the Playwright storage state JSON file with authenticated cookies.",
    )
    parser.add_argument(
        "--max-posts",
        type=int,
        default=10,
        help="Maximum number of recent activity items to capture.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run the browser in headed mode for debugging.",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write the scraped data as JSON.",
    )
    parser.add_argument(
        "--scroll-runs",
        type=int,
        default=12,
        help="How many auto-scroll passes to perform on the main profile page.",
    )
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()
    data = asyncio.run(
        scrape_linkedin_profile(
            args.url,
            storage_state=args.storage_state,
            headless=not args.headed,
            max_posts=args.max_posts,
            scroll_runs=args.scroll_runs,
        )
    )
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Wrote profile snapshot to {output_path.resolve()}")
    else:
        print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
