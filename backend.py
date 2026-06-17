## 🧠 `backend.py````python
# backend.py
# Logic: URL collection, JS auditing (static + Playwright), data processing, export

import io
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JSAuditBot/1.0)"}

SKIP_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".eot", ".ico",
    ".mp4", ".mp3", ".zip", ".tar", ".gz", ".exe", ".dmg",
}

def detect_input_type(url: str) -> str:
    """Returns 'sitemap' or 'root' based on the URL pattern."""
    url_lower = url.lower().strip()
    if url_lower.endswith(".xml") or "sitemap" in url_lower:
        return "sitemap"
    return "root"

# ─────────────────────────────────────────────────────────────────────────────
# URL COLLECTION — SITEMAP
# ─────────────────────────────────────────────────────────────────────────────

def parse_sitemap(sitemap_url: str, visited: set = None) -> list:
    """
    Recursively parse a sitemap or sitemap-index and return all page URLs.
    Handles nested sitemap indexes automatically.
    """
    if visited is None:
        visited = set()
    if sitemap_url in visited:
        return []
    visited.add(sitemap_url)

    urls = []
    try:
        resp = requests.get(sitemap_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        tag = root.tag.lower()

        if "sitemapindex" in tag:
            # Sitemap index: recurse into each child sitemap
            for el in root.iter():
                if el.tag.endswith("}loc") or el.tag == "loc":
                    child = (el.text or "").strip()
                    if child:
                        urls.extend(parse_sitemap(child, visited))
        else:
            # Regular sitemap
            for el in root.iter():
                if el.tag.endswith("}loc") or el.tag == "loc":
                    page_url = (el.text or "").strip()
                    if not page_url:
                        continue
                    if page_url.endswith(".xml") or "sitemap" in page_url.lower():
                        urls.extend(parse_sitemap(page_url, visited))
                    else:
                        urls.append(page_url)

    except ET.ParseError:
        # Fallback: parse with BeautifulSoup if XML is malformed
        try:
            soup = BeautifulSoup(resp.text, "lxml")
            for loc in soup.find_all("loc"):
                text = loc.get_text(strip=True)
                if text:
                    urls.append(text)
        except Exception:
            pass
    except Exception:
        pass

    # Deduplicate while preserving order
    return list(dict.fromkeys(urls))

# ─────────────────────────────────────────────────────────────────────────────
# URL COLLECTION — ROOT DOMAIN CRAWL
# ─────────────────────────────────────────────────────────────────────────────

def crawl_root_url(root_url: str, progress_callback=None) -> list:
    """
    BFS crawl from a root URL — collects ALL internal page URLs.
    No URL cap. Follows same-domain links only.
    """
    base_domain = urlparse(root_url).netloc
    visited = set()
    to_visit = [root_url]

    while to_visit:
        url = to_visit.pop(0).split("#")[0]  # Strip fragments
        if url in visited:
            continue

        path = urlparse(url).path.lower()
        if any(path.endswith(ext) for ext in SKIP_EXTENSIONS):
            continue

        visited.add(url)
        if progress_callback:
            progress_callback(url, len(visited))

        try:
            resp = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link["href"].strip()
                if not href or href.startswith(("mailto:", "tel:", "javascript:")):
                    continue
                full = urljoin(url, href).split("#")[0]
                parsed = urlparse(full)
                if parsed.netloc == base_domain and full not in visited:
                    if not any(parsed.path.lower().endswith(ext) for ext in SKIP_EXTENSIONS):
                        to_visit.append(full)
        except Exception:
            continue

    return list(visited)

# ─────────────────────────────────────────────────────────────────────────────
# JS AUDIT — STATIC (requests + BeautifulSoup, no JS rendering)
# ─────────────────────────────────────────────────────────────────────────────

def _audit_page_static(url: str) -> dict:
    """Audit JavaScript elements on one URL without JS rendering."""
    result = _empty_result(url)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        _parse_scripts(soup.find_all("script"), url, result)
        result["status"] = "ok"
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    return result

def audit_urls_static(urls: list, progress_callback=None) -> tuple:
    """Audit all URLs without JS rendering. Returns (results, screenshot=None)."""
    results = []
    for i, url in enumerate(urls):
        results.append(_audit_page_static(url))
        if progress_callback:
            progress_callback(i + 1, len(urls), url)
    return results, None

# ─────────────────────────────────────────────────────────────────────────────
# JS AUDIT — PLAYWRIGHT (headless Chromium, full JS rendering)
# ─────────────────────────────────────────────────────────────────────────────

def audit_urls_playwright(
    urls: list,
    screenshot_url: str = None,
    progress_callback=None,
) -> tuple:
    """
    Audit all URLs with Playwright (JS rendering enabled).
    Reuses a single browser session for performance.
    Returns (results, screenshot_bytes).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ImportError(
            "Playwright not installed. Run:\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )

    results = []
    screenshot_bytes = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path="/usr/bin/chromium")
        context = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        for i, url in enumerate(urls):
            result = _empty_result(url)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)

                # Extract script metadata via in-page JS evaluation
                scripts_data = page.evaluate(
                    """() => {
                        return Array.from(document.querySelectorAll('script')).map(s => ({
                            src:         s.getAttribute('src') || '',
                            type:        s.getAttribute('type') || '',
                            hasAsync:    s.hasAttribute('async'),
                            hasDefer:    s.hasAttribute('defer'),
                            inlineLen:   s.getAttribute('src') ? 0 : s.textContent.length
                        }));
                    }"""
                )
                _parse_scripts_playwright(scripts_data, url, result)
                result["status"] = "ok"

                # Capture screenshot for first URL (or specified URL)
                if screenshot_bytes is None and (
                    screenshot_url is None or url == screenshot_url
                ):
                    try:
                        screenshot_bytes = page.screenshot(full_page=False)
                    except Exception:
                        pass

            except Exception as e:
                result["status"] = "error"
                result["error"] = str(e)

            results.append(result)
            if progress_callback:
                progress_callback(i + 1, len(urls), url)

        browser.close()

    return results, screenshot_bytes

# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _empty_result(url: str) -> dict:
    return {
        "url": url,
        "total_scripts": 0,
        "external_scripts": 0,
        "inline_scripts": 0,
        "async_scripts": 0,
        "defer_scripts": 0,
        "module_scripts": 0,
        "first_party_scripts": 0,
        "third_party_scripts": 0,
        "inline_js_chars": 0,
        "external_script_sources": [],
        "status": "pending",
        "error": "",
    }

def _parse_scripts(script_tags, page_url: str, result: dict):
    """Populate a result dict from a list of BeautifulSoup <script> tags."""
    base_domain = urlparse(page_url).netloc
    result["total_scripts"] = len(script_tags)
    for tag in script_tags:
        src = (tag.get("src") or "").strip()
        stype = (tag.get("type") or "").lower().strip()
        if src:
            result["external_scripts"] += 1
            full_src = urljoin(page_url, src)
            result["external_script_sources"].append(full_src)
            src_domain = urlparse(full_src).netloc
            if src_domain and src_domain != base_domain:
                result["third_party_scripts"] += 1
            else:
                result["first_party_scripts"] += 1
        else:
            result["inline_scripts"] += 1
            result["inline_js_chars"] += len(tag.get_text())
        if tag.has_attr("async"):
            result["async_scripts"] += 1
        if tag.has_attr("defer"):
            result["defer_scripts"] += 1
        if stype == "module":
            result["module_scripts"] += 1

def _parse_scripts_playwright(scripts_data: list, page_url: str, result: dict):
    """Populate a result dict from Playwright's JS-evaluated script list."""
    base_domain = urlparse(page_url).netloc
    result["total_scripts"] = len(scripts_data)
    for s in scripts_data:
        src = s.get("src", "").strip()
        stype = s.get("type", "").lower().strip()
        if src:
            result["external_scripts"] += 1
            full_src = urljoin(page_url, src)
            result["external_script_sources"].append(full_src)
            src_domain = urlparse(full_src).netloc
            if src_domain and src_domain != base_domain:
                result["third_party_scripts"] += 1
            else:
                result["first_party_scripts"] += 1
        else:
            result["inline_scripts"] += 1
            result["inline_js_chars"] += s.get("inlineLen", 0)
        if s.get("hasAsync"):
            result["async_scripts"] += 1
        if s.get("hasDefer"):
            result["defer_scripts"] += 1
        if stype == "module":
            result["module_scripts"] += 1

# ─────────────────────────────────────────────────────────────────────────────
# DATA PROCESSING & EXPORT
# ─────────────────────────────────────────────────────────────────────────────

def build_dataframe(results: list) -> pd.DataFrame:
    """Convert audit results list into a clean summary DataFrame."""
    rows = []
    for r in results:
        rows.append(
            {
                "URL": r["url"],
                "Total Scripts": r["total_scripts"],
                "External Scripts": r["external_scripts"],
                "Inline Scripts": r["inline_scripts"],
                "Async Scripts": r["async_scripts"],
                "Defer Scripts": r["defer_scripts"],
                "Module Scripts": r["module_scripts"],
                "1st Party Scripts": r["first_party_scripts"],
                "3rd Party Scripts": r["third_party_scripts"],
                "Inline JS Chars": r["inline_js_chars"],
                "Status": r["status"],
                "Error": r["error"],
            }
        )
    return pd.DataFrame(rows)

def build_sources_dataframe(results: list) -> pd.DataFrame:
    """Build a flat DataFrame of every external script source found."""
    rows = []
    for r in results:
        page_domain = urlparse(r["url"]).netloc
        for src in r.get("external_script_sources", []):
            src_domain = urlparse(src).netloc
            rows.append(
                {
                    "Page URL": r["url"],
                    "Script Source": src,
                    "Script Domain": src_domain,
                    "Party": "3rd Party" if src_domain != page_domain else "1st Party",
                }
            )
    return pd.DataFrame(rows)

def export_to_excel(df_summary: pd.DataFrame, df_sources: pd.DataFrame) -> bytes:
    """Export both DataFrames to a multi-sheet Excel file. Returns raw bytes."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_summary.to_excel(writer, sheet_name="JS Audit Summary", index=False)
        if not df_sources.empty:
            df_sources.to_excel(writer, sheet_name="Script Sources", index=False)
    output.seek(0)
    return output.read()
if (window.__NEXT_DATA__) {
                framework = 'Next.js';
                rendering = 'SSR/SSG (Good for SEO)';
                seo_risk = 'Low';
                note = 'Content visible to Google';
            } else if (window.__NUXT__) {
                framework = 'Nuxt.js';
                rendering = 'SSR/SSG';
                seo_risk = 'Low';
            } else if (window.React || document.querySelector('[data-reactroot]')) {
                framework = 'React (CRA)';
                rendering = 'CSR - SEO Risk';
                seo_risk = 'High';
                note = 'All content rendered via JS - Google may miss it';
            } else if (window.Vue && !window.__NUXT__) {
                const ssr = document.querySelector('[data-server-rendered="true"]');
                framework = 'Vue.js';
                rendering = ssr ? 'SSR' : 'CSR - SEO Risk';
                seo_risk = ssr ? 'Low' : 'High';
            } else if (window.angular || document.querySelector('[ng-version]')) {
                framework = 'Angular';
                rendering = 'CSR - SEO Risk';
                seo_risk = 'High';
                note = 'Angular renders via JS - needs Angular Universal for SSR';
            } else if (window.wp || document.querySelector('link[href*="wp-content"]')) {
                framework = 'WordPress';
                rendering = 'Server-Side (Good for SEO)';
                seo_risk = 'Low';
            } else if (window.Shopify) {
                framework = 'Shopify';
                rendering = 'Server-Side (Good for SEO)';
                seo_risk = 'Low';
            } else if (document.querySelector('meta[name="generator"][content*="Wix"]')) {
                framework = 'Wix';
                rendering = 'SSR';
                seo_risk = 'Low';
            }

            return { framework, rendering, seo_risk, note };
        }
    """)
except Exception:
    return {"framework": "Unknown", "rendering": "Unknown", "seo_risk": "Unknown", "note": ""}
