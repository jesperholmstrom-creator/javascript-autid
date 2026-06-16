## 🖥️ `app.py````python
# app.py
# Frontend: Streamlit UI — JS Element Auditor for SEO Consultants

import streamlit as st
import pandas as pd
import plotly.express as px

from backend import (
    audit_urls_playwright,
    audit_urls_static,
    build_dataframe,
    build_sources_dataframe,
    crawl_root_url,
    detect_input_type,
    export_to_excel,
    parse_sitemap,
)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="JS Element Auditor",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .block-container { padding-top: 2rem; }
        .stMetric { background:#f0f4f8; border-radius:8px; padding:0.5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("⚙️ Settings")
    st.divider()

    st.subheader("🕷️ Crawler Mode")
    use_js = st.toggle(
        "JavaScript Rendering (Playwright)",
        value=False,
        help=(
            "Renders each page in a real headless browser before auditing. "
            "Captures scripts injected dynamically via JS frameworks. "
            "Slower — recommended for SPAs or JS-heavy sites."
        ),
    )
    if use_js:
        st.warning(
            "JS Rendering is ON.\n\n"
            "Make sure you ran:\n```\nplaywright install chromium\n```"
        )
    else:
        st.success("Static Mode: fast HTML crawl via requests + BeautifulSoup.")

    st.subheader("📸 Screenshot")
    take_screenshot = st.toggle(
        "Capture Sample Screenshot",
        value=True,
        help="Takes a screenshot of the first URL to visualise the audited page. Requires JS Rendering.",
    )
    if take_screenshot and not use_js:
        st.info("💡 Enable JS Rendering above to activate screenshots.")

    st.divider()
    st.caption("JS Element Auditor — built for SEO consultants.\nNo URL cap. Full-site crawl.")

# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────

st.title("🔎 JavaScript Element Auditor")
st.markdown(
    "Audit every `<script>` tag across your **entire website** — "
    "external, inline, async, defer, module, 1st & 3rd party. "
    "Works from a **sitemap URL** or a **root domain**."
)
st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# INPUT
# ─────────────────────────────────────────────────────────────────────────────

st.subheader("🌐 Target URL")

col_url, col_mode = st.columns([4, 1])

with col_url:
    input_url = st.text_input(
        label="Enter sitemap or root URL",
        placeholder="https://example.com/sitemap.xml   or   https://example.com",
        label_visibility="collapsed",
    )

with col_mode:
    override = st.selectbox(
        "Mode",
        ["🔍 Auto-detect", "🗺️ Sitemap", "🌱 Root URL"],
        label_visibility="visible",
    )

# Live hint
if input_url.strip():
    detected = detect_input_type(input_url.strip())
    if override == "🗺️ Sitemap":
        effective_type = "sitemap"
    elif override == "🌱 Root URL":
        effective_type = "root"
    else:
        effective_type = detected

    if effective_type == "sitemap":
        st.info("🗺️ **Sitemap mode** — will parse the XML sitemap and extract all listed URLs.")
    else:
        st.info("🌱 **Root crawl mode** — will follow all internal links across the domain.")

st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# START BUTTON
# ─────────────────────────────────────────────────────────────────────────────

run = st.button(
    "🚀 Start Full Audit",
    type="primary",
    use_container_width=True,
    disabled=not bool(input_url.strip()),
)

# ─────────────────────────────────────────────────────────────────────────────
# AUDIT PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

if run and input_url.strip():
    clean_url = input_url.strip()

    if override == "🗺️ Sitemap":
        effective_type = "sitemap"
    elif override == "🌱 Root URL":
        effective_type = "root"
    else:
        effective_type = detect_input_type(clean_url)

    # ── Step 1: Collect URLs ──────────────────────────────────────────────────
    with st.status("📡 **Step 1 / 2** — Collecting URLs…", expanded=True) as s1:
        if effective_type == "sitemap":
            st.write(f"Parsing sitemap: `{clean_url}`")
            urls = parse_sitemap(clean_url)
        else:
            st.write(f"Crawling `{clean_url}` — following all internal links…")
            live = st.empty()

            def on_crawl(url, count):
                live.markdown(f"🔗 **{count}** URLs found so far… `{url}`")

            urls = crawl_root_url(clean_url, progress_callback=on_crawl)

        if not urls:
            st.error("❌ No URLs found. Check your input and try again.")
            st.stop()

        s1.update(
            label=f"✅ **Step 1 / 2 complete** — **{len(urls)} URLs** collected.",
            state="complete",
        )

    st.info(f"**{len(urls)} pages** queued for JS audit.")

    # ── Step 2: Audit JS ──────────────────────────────────────────────────────
    with st.status("🔬 **Step 2 / 2** — Auditing JavaScript elements…", expanded=True) as s2:
        bar = st.progress(0)
        live2 = st.empty()

        def on_audit(done, total, url):
            bar.progress(done / total)
            live2.markdown(f"🔍 `{done} / {total}` — `{url}`")

        if use_js:
            shot_url = urls[0] if take_screenshot else None
            results, screenshot = audit_urls_playwright(
                urls, screenshot_url=shot_url, progress_callback=on_audit
            )
        else:
            results, screenshot = audit_urls_static(urls, progress_callback=on_audit)

        s2.update(
            label="✅ **Step 2 / 2 complete** — Audit finished!",
            state="complete",
        )

    # Build DataFrames
    df = build_dataframe(results)
    df_sources = build_sources_dataframe(results)

    st.success(f"🎉 Audit complete — **{len(df)} pages** analysed.")
    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # RESULTS
    # ─────────────────────────────────────────────────────────────────────────

    st.header("📊 Audit Results")

    # ── KPI row ───────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
    k1.metric("🌐 Pages", len(df))
    k2.metric("📜 Total Scripts", int(df["Total Scripts"].sum()))
    k3.metric("🔗 External", int(df["External Scripts"].sum()))
    k4.metric("📝 Inline", int(df["Inline Scripts"].sum()))
    k5.metric("⚡ Async", int(df["Async Scripts"].sum()))
    k6.metric("⏳ Defer", int(df["Defer Scripts"].sum()))
    k7.metric("🌍 3rd Party", int(df["3rd Party Scripts"].sum()))

    st.divider()

    # ── Charts row ────────────────────────────────────────────────────────────
    st.subheader("📉 Charts")
    c1, c2 = st.columns(2)

    with c1:
        totals = pd.DataFrame(
            {
                "Script Type": [
                    "External", "Inline", "Async",
                    "Defer", "Module", "3rd Party",
                ],
                "Count": [
                    int(df["External Scripts"].sum()),
                    int(df["Inline Scripts"].sum()),
                    int(df["Async Scripts"].sum()),
                    int(df["Defer Scripts"].sum()),
                    int(df["Module Scripts"].sum()),
                    int(df["3rd Party Scripts"].sum()),
                ],
            }
        ).sort_values("Count", ascending=False)

        fig1 = px.bar(
            totals,
            x="Script Type",
            y="Count",
            text="Count",
            color="Script Type",
            title="Total JS Elements Across All Pages",
            color_discrete_sequence=px.colors.qualitative.Plotly,
        )
        fig1.update_traces(textposition="outside")
        fig1.update_layout(showlegend=False, height=380)
        st.plotly_chart(fig1, use_container_width=True)

    with c2:
        pie_df = pd.DataFrame(
            {
                "Party": ["1st Party", "3rd Party"],
                "Count": [
                    int(df["1st Party Scripts"].sum()),
                    int(df["3rd Party Scripts"].sum()),
                ],
            }
        )
        fig2 = px.pie(
            pie_df,
            names="Party",
            values="Count",
            title="1st Party vs 3rd Party External Scripts",
            color_discrete_sequence=["#1f77b4", "#ff7f0e"],
            hole=0.35,
        )
        fig2.update_layout(height=380)
        st.plotly_chart(fig2, use_container_width=True)

    # Stacked bar per page
    st.subheader("📄 Scripts Per Page")
    MAX_BARS = 80
    chart_df = (
        df.nlargest(MAX_BARS, "Total Scripts")
        if len(df) > MAX_BARS
        else df.copy()
    )
    if len(df) > MAX_BARS:
        st.caption(
            f"Showing top {MAX_BARS} pages by total script count. "
            "All pages are included in the export."
        )

    fig3 = px.bar(
        chart_df,
        x="URL",
        y=["External Scripts", "Inline Scripts"],
        title="External vs Inline Scripts Per Page",
        barmode="stack",
        labels={"value": "Scripts", "variable": "Type"},
        color_discrete_map={
            "External Scripts": "#1f77b4",
            "Inline Scripts": "#ff7f0e",
        },
    )
    fig3.update_xaxes(
        tickangle=45,
        showticklabels=len(chart_df) <= 30,
    )
    fig3.update_layout(height=450)
    st.plotly_chart(fig3, use_container_width=True)

    st.divider()

    # ── Screenshot ────────────────────────────────────────────────────────────
    if screenshot:
        st.subheader("📸 Sample Screenshot")
        st.image(
            screenshot,
            caption=f"First audited page: {urls[0]}",
            use_column_width=True,
        )
        st.divider()

    # ── Data tables ───────────────────────────────────────────────────────────
    st.subheader("📋 Raw Audit Data")
    tab_summary, tab_sources = st.tabs(["📄 Page Summary", "🔗 All Script Sources"])

    with tab_summary:
        st.dataframe(
            df.drop(columns=["Error"], errors="ignore"),
            use_container_width=True,
            height=420,
        )

    with tab_sources:
        if df_sources.empty:
            st.info("No external scripts were found across the audited pages.")
        else:
            st.dataframe(df_sources, use_container_width=True, height=420)

    st.divider()

    # ── Export ────────────────────────────────────────────────────────────────
    st.subheader("⬇️ Export to Excel")
    excel = export_to_excel(df, df_sources)

    st.download_button(
        label="📥 Download Full Report (.xlsx)",
        data=excel,
        file_name="js_audit_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )
    st.caption(
        "Excel contains two sheets: **JS Audit Summary** (one row per page) "
        "and **Script Sources** (one row per external script found)."
    )
