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
