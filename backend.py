import io
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SEOAuditBot/2.0)"}

SKIP_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".css", ".js", ".woff", ".woff2", ".ttf", ".eot", ".ico",
    ".mp4", ".mp3", ".zip", ".tar", ".gz", ".exe", ".dmg",
}

KNOWN_VENDORS = {
    "google-analytics.com":    {"name": "Google Analytics",     "category": "Analytics",     "cwv_impact": "medium"},
    "analytics.google.com":    {"name": "Google Analytics 4",   "category": "Analytics",     "cwv_impact": "medium"},
    "googletagmanager.com":    {"name": "Google Tag Manager",   "category": "Tag Manager",   "cwv_impact": "medium"},
    "googlesyndication.com":   {"name": "Google Ads",           "category": "Advertising",   "cwv_impact": "high"},
    "googleadservices.com":    {"name": "Google Ads",           "category": "Advertising",   "cwv_impact": "high"},
    "hotjar.com":              {"name": "Hotjar",               "category": "Analytics",     "cwv_impact": "high"},
    "static.hotjar.com":       {"name": "Hotjar",               "category": "Analytics",     "cwv_impact": "high"},
    "clarity.ms":              {"name": "Microsoft Clarity",    "category": "Analytics",     "cwv_impact": "medium"},
    "connect.facebook.net":    {"name": "Meta Pixel",           "category": "Marketing",     "cwv_impact": "high"},
    "facebook.net":            {"name": "Meta Pixel",           "category": "Marketing",     "cwv_impact": "high"},
    "intercom.io":             {"name": "Intercom",             "category": "Chat",          "cwv_impact": "high"},
    "widget.intercom.io":      {"name": "Intercom",             "category": "Chat",          "cwv_impact": "high"},
    "crisp.chat":              {"name": "Crisp Chat",           "category": "Chat",          "cwv_impact": "medium"},
    "tawk.to":                 {"name": "Tawk.to",              "category": "Chat",          "cwv_impact": "medium"},
    "vwo.com":                 {"name": "VWO",                  "category": "A/B Testing",   "cwv_impact": "high"},
    "optimizely.com":          {"name": "Optimizely",           "category": "A/B Testing",   "cwv_impact": "high"},
    "cdn.optimizely.com":      {"name": "Optimizely",           "category": "A/B Testing",   "cwv_impact": "high"},
    "hubspot.com":             {"name": "HubSpot",              "category": "Marketing",     "cwv_impact": "high"},
    "hs-scripts.com":          {"name": "HubSpot",              "category": "Marketing",     "cwv_impact": "high"},
    "js.hs-scripts.com":       {"name": "HubSpot",              "category": "Marketing",     "cwv_impact": "high"},
    "klaviyo.com":             {"name": "Klaviyo",              "category": "Marketing",     "cwv_impact": "medium"},
    "static.klaviyo.com":      {"name": "Klaviyo",              "category": "Marketing",     "cwv_impact": "medium"},
    "mailchimp.com":           {"name": "Mailchimp",            "category": "Marketing",     "cwv_impact": "low"},
    "trustpilot.com":          {"name": "Trustpilot",           "category": "Reviews",       "cwv_impact": "medium"},
    "widget.trustpilot.com":   {"name": "Trustpilot",           "category": "Reviews",       "cwv_impact": "medium"},
    "yotpo.com":               {"name": "Yotpo",                "category": "Reviews",       "cwv_impact": "medium"},
    "cookiebot.com":           {"name": "Cookiebot",            "category": "Consent",       "cwv_impact": "medium"},
    "onetrust.com":            {"name": "OneTrust",             "category": "Consent",       "cwv_impact": "medium"},
    "cookiefirst.com":         {"name": "CookieFirst",          "category": "Consent",       "cwv_impact": "medium"},
    "usercentrics.eu":         {"name": "Usercentrics",         "category": "Consent",       "cwv_impact": "medium"},
    "sentry.io":               {"name": "Sentry",               "category": "Error Tracking","cwv_impact": "low"},
    "bugsnag.com":             {"name": "Bugsnag",              "category": "Error Tracking","cwv_impact": "low"},
    "cdn.shopify.com":         {"name": "Shopify",              "category": "E-commerce",    "cwv_impact": "medium"},
    "segment.com":             {"name": "Segment",              "category": "Analytics",     "cwv_impact": "medium"},
    "cdn.segment.com":         {"name": "Segment",              "category": "Analytics",     "cwv_impact": "medium"},
    "jquery.com":              {"name": "jQuery",               "category": "Library",       "cwv_impact": "low"},
    "code.jquery.com":         {"name": "jQuery",               "category": "Library",       "cwv_impact": "low"},
    "bootstrapcdn.com":        {"name": "Bootstrap",            "category": "Library",       "cwv_impact": "low"},
    "cdn.jsdelivr.net":        {"name": "jsDelivr CDN",         "category": "CDN",           "cwv_impact": "low"},
    "unpkg.com":               {"name": "UNPKG CDN",            "category": "CDN",           "cwv_impact": "low"},
    "cloudflare.com":          {"name": "Cloudflare",           "category": "CDN/Security",  "cwv_impact": "low"},
    "recaptcha.net":           {"name": "reCAPTCHA",            "category": "Security",      "cwv_impact": "medium"},
    "gstatic.com":             {"name": "Google Static",        "category": "Google",        "cwv_impact": "low"},
    "snap.licdn.com":          {"name": "LinkedIn Insight",     "category": "Marketing",     "cwv_impact": "medium"},
    "analytics.tiktok.com":    {"name": "TikTok Pixel",         "category": "Marketing",     "cwv_impact": "medium"},
    "sc-static.net":           {"name": "Snapchat Pixel",       "category": "Marketing",     "cwv_impact": "medium"},
    "mouseflow.com":           {"name": "Mouseflow",            "category": "Analytics",     "cwv_impact": "high"},
    "fullstory.com":           {"name": "FullStory",            "category": "Analytics",     "cwv_impact": "high"},
    "logrocket.com":           {"name": "LogRocket",            "category": "Analytics",     "cwv_impact": "medium"},
}


def detect_input_type(url: str) -> str:
    url_lower = url.lower().strip()
    if url_lower.endswith(".xml") or "sitemap" in url_lower:
        return "sitemap"
    return "root"


def parse_sitemap(sitemap_url: str, visited: set = None) -> list:
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
            for el in root.iter():
                if el.tag.endswith("}loc") or el.tag == "loc":
                    child = (el.text or "").strip()
                    if child:
                        urls.extend(parse_sitemap(child, visited))
        else:
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
    return list(dict.fromkeys(urls))


def crawl_root_url(root_url: str, progress_callback=None) -> list:
    base_domain = urlparse(root_url).netloc
    visited = set()
    to_visit = [root_url]
    while to_visit:
        url = to_visit.pop(0).split("#")[0]
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
            if "text/html" not in resp.headers.get("content-type", ""):
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


def identify_vendor(script_url: str) -> dict:
    try:
        domain = urlparse(script_url).netloc.lower()
        for vendor_domain, info in KNOWN_VENDORS.items():
            if vendor_domain in domain:
                return info
    except Exception:
        pass
    return {"name": "Unknown", "category": "Other", "cwv_impact": "unknown"}


def detect_framework(page) -> dict:
    try:
        return page.evaluate("""
            () => {
                let framework = 'Unknown / Static HTML';
                let rendering = 'Server-Side';
                let seo_risk = 'Low';
                let note = '';

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


def check_seo_elements(url: str, page) -> dict:
    result = {
        "title_in_html": False,
        "title_in_rendered": False,
        "title_js_injected": False,
        "meta_desc_in_html": False,
        "meta_desc_in_rendered": False,
        "meta_desc_js_injected": False,
        "h1_in_html": False,
        "h1_in_rendered": False,
        "h1_js_injected": False,
        "canonical_in_html": False,
        "canonical_in_rendered": False,
        "schema_in_html": False,
        "schema_in_rendered": False,
        "schema_js_injected": False,
        "robots_meta_in_html": False,
        "noindex_risk": False,
        "seo_score": 10,
    }
    try:
        raw_resp = requests.get(url, headers=HEADERS, timeout=15)
        raw_soup = BeautifulSoup(raw_resp.text, "html.parser")
        result["title_in_html"] = bool(raw_soup.find("title") and raw_soup.find("title").get_text(strip=True))
        result["meta_desc_in_html"] = bool(raw_soup.find("meta", attrs={"name": "description"}))
        result["h1_in_html"] = bool(raw_soup.find("h1") and raw_soup.find("h1").get_text(strip=True))
        result["canonical_in_html"] = bool(raw_soup.find("link", attrs={"rel": "canonical"}))
        result["schema_in_html"] = bool(raw_soup.find("script", attrs={"type": "application/ld+json"}))
        robots = raw_soup.find("meta", attrs={"name": "robots"})
        if robots:
            result["robots_meta_in_html"] = True
            content = (robots.get("content") or "").lower()
            result["noindex_risk"] = "noindex" in content
    except Exception:
        pass

    try:
        rendered = page.evaluate("""
            () => ({
                title:     document.title || '',
                meta_desc: (document.querySelector('meta[name="description"]') || {}).content || '',
                h1:        (document.querySelector('h1') || {}).textContent || '',
                canonical: !!(document.querySelector('link[rel="canonical"]')),
                schema:    !!(document.querySelector('script[type="application/ld+json"]'))
            })
        """)
        result["title_in_rendered"]     = bool(rendered.get("title"))
        result["meta_desc_in_rendered"] = bool(rendered.get("meta_desc"))
        result["h1_in_rendered"]        = bool((rendered.get("h1") or "").strip())
        result["canonical_in_rendered"] = rendered.get("canonical", False)
        result["schema_in_rendered"]    = rendered.get("schema", False)
        result["title_js_injected"]     = not result["title_in_html"]     and result["title_in_rendered"]
        result["meta_desc_js_injected"] = not result["meta_desc_in_html"] and result["meta_desc_in_rendered"]
        result["h1_js_injected"]        = not result["h1_in_html"]        and result["h1_in_rendered"]
        result["schema_js_injected"]    = not result["schema_in_html"]    and result["schema_in_rendered"]
    except Exception:
        pass

    score = 10
    if result["title_js_injected"]:     score -= 2
    if result["h1_js_injected"]:        score -= 3
    if result["meta_desc_js_injected"]: score -= 1
    if result["schema_js_injected"]:    score -= 2
    if not result["title_in_rendered"]: score -= 2
    if not result["h1_in_rendered"]:    score -= 2
    if result["noindex_risk"]:          score -= 5
    result["seo_score"] = max(0, score)
    return result


def analyze_hidden_content(page) -> dict:
    try:
        return page.evaluate("""
            () => {
                const result = {
                    accordions_count: 0,
                    tabs_count: 0,
                    dropdown_links: 0,
                    hidden_word_count: 0,
                    issues: []
                };

                const accordionEls = document.querySelectorAll(
                    'details, .accordion, .accordion-item, [data-toggle="collapse"], ' +
                    '[aria-expanded="false"], .faq-item, .faq-question, .collapsible'
                );
                result.accordions_count = accordionEls.length;
                if (accordionEls.length > 0) {
                    result.issues.push(accordionEls.length + ' accordion/FAQ elements found - content may be hidden from Google');
                }

                const tabEls = document.querySelectorAll(
                    '[role="tab"], .tab, .nav-tab, [data-toggle="tab"], .tab-item, .tab-link'
                );
                const inactiveTabs = Array.from(tabEls).filter(el =>
                    !el.classList.contains('active') && el.getAttribute('aria-selected') !== 'true'
                );
                result.tabs_count = tabEls.length;
                if (inactiveTabs.length > 0) {
                    result.issues.push(inactiveTabs.length + ' inactive tabs - hidden content indexed with lower weight');
                }

                const dropdownEls = document.querySelectorAll(
                    '.dropdown-menu, .sub-menu, nav ul ul, [data-toggle="dropdown"] + ul'
                );
                let totalDropdownLinks = 0;
                dropdownEls.forEach(el => {
                    totalDropdownLinks += el.querySelectorAll('a').length;
                });
                result.dropdown_links = totalDropdownLinks;
                if (totalDropdownLinks > 0) {
                    result.issues.push(totalDropdownLinks + ' dropdown navigation links - Google may never crawl these!');
                }

                const hiddenEls = document.querySelectorAll(
                    '[style*="display:none"], [style*="display: none"], [hidden], .hidden, .d-none, [aria-hidden="true"]'
                );
                let wordCount = 0;
                hiddenEls.forEach(el => {
                    const words = el.textContent.trim().split(/\\s+/).filter(w => w.length > 2);
                    wordCount += words.length;
                });
                result.hidden_word_count = wordCount;
                if (wordCount > 200) {
                    result.issues.push(wordCount + ' hidden words on page - may affect content relevance score');
                }

                return result;
            }
        """)
    except Exception:
        return {
            "accordions_count": 0,
            "tabs_count": 0,
            "dropdown_links": 0,
            "hidden_word_count": 0,
            "issues": [],
        }


def analyze_gtm_containers(script_sources: list) -> list:
    gtm_results = []
    gtm_ids = set()
    for src in script_sources:
        matches = re.findall(r'GTM-[A-Z0-9]+', src)
        gtm_ids.update(matches)
    for gtm_id in gtm_ids:
        result = {
            "id": gtm_id,
            "ga4_ids": [],
            "ua_ids": [],
            "has_meta_pixel": False,
            "has_google_ads": False,
            "google_ads_ids": [],
            "has_ab_testing": False,
            "ab_tools": [],
            "has_chat": False,
            "chat_tools": [],
            "duplicate_ga4": False,
            "warnings": [],
            "total_tags_found": 0,
        }
        try:
            url = f"https://www.googletagmanager.com/gtm.js?id={gtm_id}"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            content = resp.text
            ga4 = list(set(re.findall(r'G-[A-Z0-9]{8,12}', content)))
            result["ga4_ids"] = ga4
            if len(ga4) > 1:
                result["duplicate_ga4"] = True
                result["warnings"].append(f"Duplicate GA4 tracking IDs found: {len(ga4)} IDs")
            ua = list(set(re.findall(r'UA-\d+-\d+', content)))
            result["ua_ids"] = ua
            if ua:
                result["warnings"].append(f"Universal Analytics ({ua[0]}) found - should be replaced by GA4")
            if "facebook" in content.lower() or "fbq" in content or "fbevents" in content:
                result["has_meta_pixel"] = True
            aw = list(set(re.findall(r'AW-\d+', content)))
            result["google_ads_ids"] = aw
            result["has_google_ads"] = bool(aw)
            ab_tools = []
            if "optimizely" in content.lower():
                ab_tools.append("Optimizely")
            if "vwo" in content.lower() or "visualwebsiteoptimizer" in content.lower():
                ab_tools.append("VWO")
            if "abtasty" in content.lower():
                ab_tools.append("AB Tasty")
            if "kameleoon" in content.lower():
                ab_tools.append("Kameleoon")
            result["ab_tools"] = ab_tools
            result["has_ab_testing"] = bool(ab_tools)
            if ab_tools:
                result["warnings"].append(f"A/B testing tools in GTM: {', '.join(ab_tools)} - flicker risk & inconsistent indexing")
            chat_tools = []
            if "intercom" in content.lower():
                chat_tools.append("Intercom")
            if "zendesk" in content.lower():
                chat_tools.append("Zendesk")
            if "crisp" in content.lower():
                chat_tools.append("Crisp")
            if "tawk" in content.lower():
                chat_tools.append("Tawk.to")
            if "drift" in content.lower():
                chat_tools.append("Drift")
            result["chat_tools"] = chat_tools
            result["has_chat"] = bool(chat_tools)
            result["total_tags_found"] = (
                len(ga4) + len(ua)
                + (1 if result["has_meta_pixel"] else 0)
                + len(aw) + len(ab_tools) + len(chat_tools)
            )
        except Exception:
            result["warnings"].append("Could not read GTM container")
        gtm_results.append(result)
    return gtm_results


def detect_script_conflicts(script_sources: list, page_url: str) -> list:
    conflicts = []
    jquery_versions = []
    for src in script_sources:
        m = re.search(r'jquery-([\d.]+)(.min)?.js', src, re.IGNORECASE)
        if m:
            jquery_versions.append(m.group(1))
    if len(jquery_versions) > 1:
        conflicts.append(f"jQuery loaded {len(jquery_versions)} times: v{', v'.join(jquery_versions)}")
    ga4_direct = [s for s in script_sources if "googletagmanager.com/gtag" in s or "google-analytics.com" in s]
    if len(ga4_direct) > 1:
        conflicts.append(f"Google Analytics loaded {len(ga4_direct)} times directly (outside GTM)")
    chat_domains = ["intercom", "tawk", "crisp", "zendesk", "drift", "hubspot"]
    found_chats = [c for c in chat_domains if any(c in s for s in script_sources)]
    if len(found_chats) > 1:
        conflicts.append(f"Multiple chat tools active: {', '.join(found_chats)} - unnecessary CWV load")
    ab_domains = ["optimizely", "vwo", "abtasty", "kameleoon"]
    found_ab = [a for a in ab_domains if any(a in s for s in script_sources)]
    if len(found_ab) > 1:
        conflicts.append(f"Multiple A/B testing tools: {', '.join(found_ab)} - flicker risk!")
    return conflicts


def generate_recommendations(result: dict) -> list:
    recs = []
    if result.get("h1_js_injected"):
        recs.append({
            "priority": "Critical",
            "issue": "H1 injected via JavaScript",
            "impact": "Google may miss your main heading",
            "fix": "Render H1 in server-side HTML - not via JS",
        })
    if result.get("title_js_injected"):
        recs.append({
            "priority": "Critical",
            "issue": "Page Title injected via JavaScript",
            "impact": "Google may show wrong title in search results",
            "fix": "Set title tag in static HTML or via SSR",
        })
    if result.get("schema_js_injected"):
        recs.append({
            "priority": "High",
            "issue": "Schema/Structured Data injected via JavaScript",
            "impact": "Rich snippets (stars, FAQ etc.) may not show",
            "fix": "Move JSON-LD to static HTML",
        })
    if result.get("noindex_risk"):
        recs.append({
            "priority": "Critical",
            "issue": "Noindex directive found",
            "impact": "Page is NOT indexed by Google",
            "fix": "Check robots meta tag immediately",
        })
    framework_info = result.get("framework_info", {})
    if framework_info.get("seo_risk") == "High":
        recs.append({
            "priority": "Critical",
            "issue": f"CSR rendering ({framework_info.get('framework', '')})",
            "impact": "All content rendered via JS - Google must execute JS to read the page",
            "fix": "Migrate to SSR (Server-Side Rendering) or SSG (Static Generation)",
        })
    hidden = result.get("hidden_content", {})
    if hidden.get("dropdown_links", 0) > 5:
        recs.append({
            "priority": "High",
            "issue": f"{hidden['dropdown_links']} dropdown navigation links",
            "impact": "Google likely never crawls these sub-pages",
            "fix": "Ensure dropdown menus are crawlable without JavaScript",
        })
    if hidden.get("accordions_count", 0) > 0:
        recs.append({
            "priority": "Medium",
            "issue": f"{hidden['accordions_count']} accordion/FAQ elements",
            "impact": "Hidden content indexed with lower weight",
            "fix": "Ensure FAQ answers exist in HTML (not only via JS toggle)",
        })
    for gtm in result.get("gtm_analysis", []):
        for warning in gtm.get("warnings", []):
            recs.append({
                "priority": "Medium",
                "issue": f"GTM {gtm['id']}: {warning}",
                "impact": "Data errors or performance issues",
                "fix": "Review GTM container and remove duplicate/outdated tags",
            })
    for conflict in result.get("conflicts", []):
        recs.append({
            "priority": "Medium",
            "issue": f"Script conflict: {conflict}",
            "impact": "Unnecessary JS load, potential data errors",
            "fix": "Remove duplicates and consolidate via GTM",
        })
    external = result.get("external_scripts", 0)
    async_s  = result.get("async_scripts", 0)
    defer_s  = result.get("defer_scripts", 0)
    blocking = external - async_s - defer_s
    if blocking > 3:
        recs.append({
            "priority": "High",
            "issue": f"{blocking} render-blocking scripts",
            "impact": "Direct negative impact on Core Web Vitals (LCP/TBT)",
            "fix": "Add async or defer to all external script tags",
        })
    order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    recs.sort(key=lambda x: order.get(x["priority"], 9))
    return recs


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
        "vendors": [],
        "gtm_ids": [],
        "framework_info": {},
        "seo_elements": {},
        "hidden_content": {},
        "gtm_analysis": [],
        "conflicts": [],
        "recommendations": [],
        "status": "pending",
        "error": "",
    }


def _parse_scripts_base(script_tags_data, page_url: str, result: dict):
    base_domain = urlparse(page_url).netloc
    for s in script_tags_data:
        src        = s.get("src", "").strip()
        stype      = (s.get("type", "") or "").lower().strip()
        has_async  = s.get("hasAsync", False)
        has_defer  = s.get("hasDefer", False)
        inline_len = s.get("inlineLen", 0)
        if src:
            result["external_scripts"] += 1
            full_src = urljoin(page_url, src)
            result["external_script_sources"].append(full_src)
            src_domain = urlparse(full_src).netloc
            if src_domain and src_domain != base_domain:
                result["third_party_scripts"] += 1
                vendor = identify_vendor(full_src)
                result["vendors"].append({
                    "url": full_src,
                    "domain": src_domain,
                    **vendor,
                })
            else:
                result["first_party_scripts"] += 1
            if "googletagmanager.com/gtm.js" in full_src:
                gtm_ids = re.findall(r'GTM-[A-Z0-9]+', full_src)
                result["gtm_ids"].extend(gtm_ids)
        else:
            result["inline_scripts"]  += 1
            result["inline_js_chars"] += inline_len
        if has_async:
            result["async_scripts"] += 1
        if has_defer:
            result["defer_scripts"] += 1
        if stype == "module":
            result["module_scripts"] += 1
    result["total_scripts"] = result["external_scripts"] + result["inline_scripts"]


def _audit_page_static(url: str) -> dict:
    result = _empty_result(url)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        script_tags = []
        for tag in soup.find_all("script"):
            script_tags.append({
                "src":       tag.get("src", ""),
                "type":      tag.get("type", ""),
                "hasAsync":  tag.has_attr("async"),
                "hasDefer":  tag.has_attr("defer"),
                "inlineLen": len(tag.get_text()) if not tag.get("src") else 0,
            })
        _parse_scripts_base(script_tags, url, result)
        result["conflicts"]       = detect_script_conflicts(result["external_script_sources"], url)
        result["recommendations"] = generate_recommendations(result)
        result["status"] = "ok"
    except Exception as e:
        result["status"] = "error"
        result["error"]  = str(e)
    return result


def audit_urls_static(urls: list, progress_callback=None) -> tuple:
    results = []
    for i, url in enumerate(urls):
        results.append(_audit_page_static(url))
        if progress_callback:
            progress_callback(i + 1, len(urls), url)
    return results, None


def audit_urls_playwright(
    urls: list,
    screenshot_url: str = None,
    progress_callback=None,
) -> tuple:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ImportError("Playwright not installed. Run: pip install playwright && playwright install chromium")

    results = []
    screenshot_bytes = None

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path="/usr/bin/chromium",
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        for i, url in enumerate(urls):
            result = _empty_result(url)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                scripts_data = page.evaluate("""
                    () => Array.from(document.querySelectorAll('script')).map(s => ({
                        src:       s.getAttribute('src') || '',
                        type:      s.getAttribute('type') || '',
                        hasAsync:  s.hasAttribute('async'),
                        hasDefer:  s.hasAttribute('defer'),
                        inlineLen: s.getAttribute('src') ? 0 : s.textContent.length
                    }))
                """)
                _parse_scripts_base(scripts_data, url, result)
                result["framework_info"]  = detect_framework(page)
                result["seo_elements"]    = check_seo_elements(url, page)
                result["hidden_content"]  = analyze_hidden_content(page)
                result["gtm_analysis"]    = analyze_gtm_containers(result["external_script_sources"])
                result["conflicts"]       = detect_script_conflicts(result["external_script_sources"], url)
                result["recommendations"] = generate_recommendations(result)
                result["status"] = "ok"
                if screenshot_bytes is None and (screenshot_url is None or url == screenshot_url):
                    try:
                        screenshot_bytes = page.screenshot(full_page=False)
                    except Exception:
                        pass
            except Exception as e:
                result["status"] = "error"
                result["error"]  = str(e)
            results.append(result)
            if progress_callback:
                progress_callback(i + 1, len(urls), url)

        browser.close()

    return results, screenshot_bytes


def build_dataframe(results: list) -> pd.DataFrame:
    rows = []
    for r in results:
        seo    = r.get("seo_elements", {})
        hidden = r.get("hidden_content", {})
        fw     = r.get("framework_info", {})
        recs   = r.get("recommendations", [])
        critical = sum(1 for x in recs if x.get("priority") == "Critical")
        high     = sum(1 for x in recs if x.get("priority") == "High")
        rows.append({
            "URL":               r["url"],
            "SEO Score":         seo.get("seo_score", "-"),
            "Critical Issues":   critical,
            "High Issues":       high,
            "Total Scripts":     r["total_scripts"],
            "External Scripts":  r["external_scripts"],
            "Inline Scripts":    r["inline_scripts"],
            "Async Scripts":     r["async_scripts"],
            "Defer Scripts":     r["defer_scripts"],
            "3rd Party Scripts": r["third_party_scripts"],
            "Title in HTML":     "Yes" if seo.get("title_in_html")     else ("JS Injected" if seo.get("title_js_injected")     else "Missing"),
            "H1 in HTML":        "Yes" if seo.get("h1_in_html")        else ("JS Injected" if seo.get("h1_js_injected")        else "Missing"),
            "Meta Desc in HTML": "Yes" if seo.get("meta_desc_in_html") else ("JS Injected" if seo.get("meta_desc_js_injected") else "Missing"),
            "Schema in HTML":    "Yes" if seo.get("schema_in_html")    else ("JS Injected" if seo.get("schema_js_injected")    else "Missing"),
            "Noindex Risk":      "YES" if seo.get("noindex_risk") else "No",
            "Framework":         fw.get("framework", "-"),
            "Rendering":         fw.get("rendering", "-"),
            "SEO Risk":          fw.get("seo_risk", "-"),
            "Dropdown Links":    hidden.get("dropdown_links", 0),
            "Accordions/FAQ":    hidden.get("accordions_count", 0),
            "GTM Found":         "Yes" if r.get("gtm_ids") else "No",
            "Status":            r["status"],
        })
    return pd.DataFrame(rows)


def build_vendors_dataframe(results: list) -> pd.DataFrame:
    rows = []
    for r in results:
        for v in r.get("vendors", []):
            rows.append({
                "Page URL":   r["url"],
                "Script URL": v.get("url", ""),
                "Vendor":     v.get("name", "Unknown"),
                "Category":   v.get("category", "Other"),
                "CWV Impact": v.get("cwv_impact", "unknown"),
            })
    return pd.DataFrame(rows)


def build_recommendations_dataframe(results: list) -> pd.DataFrame:
    rows = []
    for r in results:
        for rec in r.get("recommendations", []):
            rows.append({
                "URL":      r["url"],
                "Priority": rec.get("priority", ""),
                "Issue":    rec.get("issue", ""),
                "Impact":   rec.get("impact", ""),
                "Fix":      rec.get("fix", ""),
            })
    return pd.DataFrame(rows)


def export_to_excel(df_main, df_vendors, df_recs) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_main.to_excel(writer, sheet_name="JS Audit Summary", index=False)
        if not df_vendors.empty:
            df_vendors.to_excel(writer, sheet_name="Vendor Analysis", index=False)
        if not df_recs.empty:
            df_recs.to_excel(writer, sheet_name="Recommendations", index=False)
    output.seek(0)
    return output.read()