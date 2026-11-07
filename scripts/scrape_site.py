"""
µLearn Concierge — Website Scraper
Fetches public pages from mulearn.org and writes structured content to knowledge/website.md.

Usage:
    python scripts/scrape_site.py

Approach:
1. Respects robots.txt (polite crawling)
2. Tries plain requests + BeautifulSoup first
3. Falls back to Playwright for JS-rendered pages
4. If both fail, prints instructions for manual content addition

Note: mulearn.org is likely a Next.js SPA, so plain requests may return
minimal content. The fallback and manual options handle this gracefully.
"""

import os
import sys
import time
from datetime import datetime
from urllib.robotparser import RobotFileParser
from urllib.parse import urljoin

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: Missing dependencies. Run: pip install requests beautifulsoup4")
    sys.exit(1)


# Pages to scrape
TARGET_URLS = [
    "https://mulearn.org/",
    "https://mulearn.org/about",
    "https://mulearn.org/events",
    "https://mulearn.org/interest-groups",
    "https://mulearn.org/careers",
]

DELAY_SECONDS = 2  # Polite delay between requests
USER_AGENT = "MULearnConciergeBot/1.0 (educational project)"
MIN_CONTENT_LENGTH = 200  # Minimum chars to consider a page successfully scraped

KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge")
OUTPUT_FILE = os.path.join(KNOWLEDGE_DIR, "website.md")


def check_robots_txt(url):
    """Check if we're allowed to crawl the URL per robots.txt."""
    try:
        rp = RobotFileParser()
        robots_url = urljoin(url, "/robots.txt")
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(USER_AGENT, url)
    except Exception as e:
        print(f"  Warning: Could not read robots.txt: {e}")
        return True  # Assume allowed if robots.txt is inaccessible


def scrape_with_requests(url):
    """Try scraping with plain requests + BeautifulSoup."""
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # Remove script, style, nav, footer tags
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        # Extract text content
        text = soup.get_text(separator="\n", strip=True)

        # Clean up excessive whitespace
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        text = "\n".join(lines)

        return text if len(text) >= MIN_CONTENT_LENGTH else None

    except Exception as e:
        print(f"  requests failed: {e}")
        return None


def scrape_with_playwright(url):
    """Fallback: scrape with Playwright for JS-rendered pages."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  Playwright not installed. Install with:")
        print("    pip install playwright && playwright install chromium")
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Wait for content to render
            page.wait_for_timeout(3000)
            
            # Extract text
            content = page.evaluate("""() => {
                // Remove unwanted elements
                const remove = document.querySelectorAll('script, style, nav, footer, header, noscript');
                remove.forEach(el => el.remove());
                return document.body.innerText;
            }""")
            
            browser.close()
            
            if content and len(content.strip()) >= MIN_CONTENT_LENGTH:
                return content.strip()
            return None

    except Exception as e:
        print(f"  Playwright failed: {e}")
        return None


def scrape_page(url):
    """Scrape a single page, trying requests first, then Playwright."""
    print(f"\nScraping: {url}")

    if not check_robots_txt(url):
        print(f"  Blocked by robots.txt, skipping.")
        return None

    # Try requests first
    content = scrape_with_requests(url)
    if content:
        print(f"  ✓ Got {len(content)} chars via requests")
        return content

    print("  Content too thin via requests, trying Playwright...")
    content = scrape_with_playwright(url)
    if content:
        print(f"  ✓ Got {len(content)} chars via Playwright")
        return content

    print(f"  ✗ Could not extract enough content from {url}")
    return None


def build_markdown(pages):
    """Build the knowledge markdown file from scraped pages."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    lines = [
        "# µLearn — Website Knowledge Base",
        f"> Source: https://mulearn.org",
        f"> Last updated: {now}",
        f"> Method: Auto-scraped by scripts/scrape_site.py",
        "",
    ]

    for url, content in pages.items():
        if content:
            # Use URL path as section title
            path = url.replace("https://mulearn.org", "").strip("/")
            title = path.replace("-", " ").title() if path else "Home"
            lines.append(f"## {title}")
            lines.append("")
            lines.append(content)
            lines.append("")

    return "\n".join(lines)


def main():
    print("=" * 60)
    print("µLearn Concierge — Website Scraper")
    print("=" * 60)

    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)

    pages = {}
    for url in TARGET_URLS:
        content = scrape_page(url)
        pages[url] = content
        time.sleep(DELAY_SECONDS)

    # Check if we got any content
    scraped_count = sum(1 for c in pages.values() if c)

    if scraped_count == 0:
        print("\n" + "=" * 60)
        print("⚠  Could not scrape any content from mulearn.org.")
        print("   The site is likely JavaScript-rendered (Next.js/React).")
        print()
        print("   Options:")
        print("   1. Install Playwright: pip install playwright && playwright install chromium")
        print("   2. Manually add content to knowledge/website.md")
        print("      (Copy text from mulearn.org pages and format as markdown)")
        print("   3. The existing knowledge/website.md will be used as-is.")
        print("=" * 60)
        
        if os.path.exists(OUTPUT_FILE):
            print(f"\n  Existing {OUTPUT_FILE} preserved.")
        return

    # Write output
    markdown = build_markdown(pages)

    # Backup existing file
    if os.path.exists(OUTPUT_FILE):
        backup = OUTPUT_FILE + ".bak"
        os.replace(OUTPUT_FILE, backup)
        print(f"\n  Backed up existing file to {backup}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"\n✓ Wrote {scraped_count}/{len(TARGET_URLS)} pages to {OUTPUT_FILE}")
    print(f"  Total size: {len(markdown)} chars")


if __name__ == "__main__":
    main()
