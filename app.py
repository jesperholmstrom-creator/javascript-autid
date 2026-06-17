## `app.py````python
import streamlit as st
import pandas as pd
import plotly.express as px

from backend import (
    audit_urls_playwright,
    audit_urls_static,
    build_dataframe,
    build_vendors_dataframe,
    build_recommendations_dataframe,
    crawl_root_url,
    detect_input_type,
    export_to_excel,
    parse_sitemap,
)

st.set_page_config(
    page_title="SEO JS Auditor",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("Settings")
    st.divider()
    st.subheader("Crawler Mode")
    use_js = st.toggle(
        "JavaScript Rendering (Playwright)",
        value=False,
        help="Enables framework detection, SEO element comparison, hidden content and GTM analysis.",
    )
    if use_js:
        st.warning("JS Rendering ON\nRun: `playwright install chromium`")
        st.info("Enables:\n- Framework detection\n- SEO element comparison\n- Hidden content\n- GTM analysis")
    else:
        st.success("Static mode - fast basic analysis")
    st.subheader("Screenshot")
    take_screenshot = st.toggle("Capture screenshot", value=True)
    st.divider()
    st.caption("SEO JS Auditor v2.0")

st.title("SEO JavaScript Auditor")
st.markdown(
    "Vendor identification, GTM analysis, hidden content detection, "
    "framework detection and automatic recommendations."
)
st.divider()

st.subheader("Target URL")
col_url, col_mode = st.columns([4, 1])
with col_url:
    input_url = st.text_input(
        "URL",
        placeholder="https://example.com/sitemap.xml  or  https://example.com",
        label_visibility="collapsed",
    )
with col_mode:
    override = st.selectbox("Type", ["Auto", "Sitemap", "Root URL"])

if input_url.strip():
    detected = detect_input_type(input_url.strip())
    eff = "sitemap" if override == "Sitemap" else "root" if override == "Root URL" else detected
    if eff == "sitemap":
        st.info("Sitemap mode — fetches all URLs from XML sitemap")
    else:
        st.info("Root crawl mode — follows all internal links")

st.divider()
run = st.button(
    "Start Audit",
    type="primary",
    use_container_width=True,
    disabled=not bool(input_url.strip()),
)

if run and input_url.strip():
    clean_url = input_url.strip()
    eff = "sitemap" if override == "Sitemap" else "root" if override == "Root URL" else detect_input_type(clean_url)

    with st.status("Step 1/2 — Collecting URLs...", expanded=True) as s1:
        if eff == "sitemap":
            urls = parse_sitemap(clean_url)
        else:
            live = st.empty()
            def on_crawl(url, count):
                live.markdown(f"{count} URLs found... `{url}`")
            urls = crawl_root_url(clean_url, progress_callback=on_crawl)
        if not urls:
            st.error("No URLs found.")
            st.stop()
        s1.update(label=f"Step 1/2 complete — {len(urls)} URLs collected", state="complete")

    st.info(f"**{len(urls)} pages** will be analysed.")

    with st.status("Step 2/2 — Analysing JavaScript...", expanded=True) as s2:
        bar   = st.progress(0)
        live2 = st.empty()
        def on_audit(done, total, url):
            bar.progress(done / total)
            live2.markdown(f"{done}/{total} — `{url}`")
        if use_js:
            shot_url = urls[0] if take_screenshot else None
            results, screenshot = audit_urls_playwright(urls, screenshot_url=shot_url, progress_callback=on_audit)
        else:
            results, screenshot = audit_urls_static(urls, progress_callback=on_audit)
        s2.update(label="Step 2/2 complete — Analysis done!", state="complete")

    df         = build_dataframe(results)
    df_vendors = build_vendors_dataframe(results)
    df_recs    = build_recommendations_dataframe(results)

    st.success(f"**{len(df)} pages** analysed!")
    st.divider()

    st.header("Automatic Recommendations")

    if not df_recs.empty:
        critical_count = len(df_recs[df_recs["Priority"] == "Critical"])
        high_count     = len(df_recs[df_recs["Priority"] == "High"])
        medium_count   = len(df_recs[df_recs["Priority"] == "Medium"])

        c1, c2, c3 = st.columns(3)
        c1.metric("Critical", critical_count)
        c2.metric("High",     high_count)
        c3.metric("Medium",   medium_count)

        for _, row in df_recs.drop_duplicates(subset=["Priority", "Issue"]).iterrows():
            priority = row["Priority"]
            icon = "🔴" if priority == "Critical" else "🟠" if priority == "High" else "🟡"
            with st.expander(f"{icon} {priority} — {row['Issue']}"):
                st.markdown(f"**Impact:** {row['Impact']}")
                st.markdown(f"**Fix:** {row['Fix']}")
                affected = df_recs[df_recs["Issue"] == row["Issue"]]["URL"].nunique()
                st.markdown(f"**Affects:** {affected} page(s)")
    else:
        st.success("No critical issues found!")

    st.divider()

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Overview",
        "Vendors",
        "SEO Elements",
        "Hidden Content",
        "Framework & GTM",
        "Raw Data",
    ])

    with tab1:
        st.subheader("Summary")
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("Pages",         len(df))
        k2.metric("Total Scripts", int(df["Total Scripts"].sum()))
        k3.metric("External",      int(df["External Scripts"].sum()))
        k4.metric("3rd Party",     int(df["3rd Party Scripts"].sum()))
        k5.metric("Async",         int(df["Async Scripts"].sum()))
        k6.metric("Defer",         int(df["Defer Scripts"].sum()))

        col_c1, col_c2 = st.columns(2)
        with col_c1:
            chart_data = pd.DataFrame({
                "Type":  ["External", "Inline", "Async", "Defer", "3rd Party"],
                "Count": [
                    int(df["External Scripts"].sum()),
                    int(df["Inline Scripts"].sum()),
                    int(df["Async Scripts"].sum()),
                    int(df["Defer Scripts"].sum()),
                    int(df["3rd Party Scripts"].sum()),
                ],
            }).sort_values("Count", ascending=False)
            fig = px.bar(chart_data, x="Type", y="Count", color="Type",
                         title="Script types total", text="Count",
                         color_discrete_sequence=px.colors.qualitative.Plotly)
            fig.update_traces(textposition="outside")
            fig.update_layout(showlegend=False, height=350)
            st.plotly_chart(fig, use_container_width=True)

        with col_c2:
            first_party = int(df["External Scripts"].sum()) - int(df["3rd Party Scripts"].sum())
            pie_data = pd.DataFrame({
                "Party": ["1st Party", "3rd Party"],
                "Count": [max(first_party, 0), int(df["3rd Party Scripts"].sum())],
            })
            fig2 = px.pie(pie_data, names="Party", values="Count",
                          title="1st vs 3rd Party scripts",
                          color_discrete_sequence=["#1f77b4", "#ff7f0e"], hole=0.4)
            fig2.update_layout(height=350)
            st.plotly_chart(fig2, use_container_width=True)

        if screenshot:
            st.subheader("Screenshot")
            st.image(screenshot, caption=f"First page: {urls[0]}", use_column_width=True)

    with tab2:
        st.subheader("Vendor Analysis")
        if df_vendors.empty:
            st.info("No known vendors found.")
        else:
            v1, v2, v3 = st.columns(3)
            v1.metric("Unique vendors",    df_vendors["Vendor"].nunique())
            v2.metric("3rd party scripts", len(df_vendors))
            v3.metric("Categories",        df_vendors["Category"].nunique())

            col_v1, col_v2 = st.columns(2)
            with col_v1:
                vendor_counts = df_vendors.groupby("Vendor").size().reset_index(name="Pages")
                vendor_counts = vendor_counts.sort_values("Pages", ascending=False).head(15)
                fig_v = px.bar(vendor_counts, x="Pages", y="Vendor",
                               orientation="h", title="Most common vendors",
                               color="Pages", color_continuous_scale="Blues")
                fig_v.update_layout(height=400, yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig_v, use_container_width=True)

            with col_v2:
                cat_counts = df_vendors.groupby("Category").size().reset_index(name="Count")
                fig_c = px.pie(cat_counts, names="Category", values="Count",
                               title="Scripts by category", hole=0.3)
                fig_c.update_layout(height=400)
                st.plotly_chart(fig_c, use_container_width=True)

            st.subheader("CWV Impact per vendor")
            cwv_order = {"high": 0, "medium": 1, "low": 2, "unknown": 3}
            df_vendors_sorted = df_vendors.drop_duplicates("Vendor").sort_values(
                "CWV Impact", key=lambda x: x.map(cwv_order)
            )
            for _, row in df_vendors_sorted.iterrows():
                impact = row["CWV Impact"]
                icon = "🔴" if impact == "high" else "🟡" if impact == "medium" else "🟢"
                st.markdown(f"{icon} **{row['Vendor']}** — {row['Category']} `{impact} CWV impact`")

    with tab3:
        st.subheader("SEO Element Visibility")
        if not use_js:
            st.warning("Enable **JavaScript Rendering** in sidebar for full SEO element analysis.")
        else:
            seo_cols  = ["URL", "Title in HTML", "H1 in HTML", "Meta Desc in HTML",
                         "Schema in HTML", "Noindex Risk", "SEO Score"]
            available = [c for c in seo_cols if c in df.columns]
            if available:
                c1, c2, c3, c4 = st.columns(4)
                if "Title in HTML"  in df.columns: c1.metric("JS Injected Title",  len(df[df["Title in HTML"]  == "JS Injected"]))
                if "H1 in HTML"     in df.columns: c2.metric("JS Injected H1",     len(df[df["H1 in HTML"]     == "JS Injected"]))
                if "Schema in HTML" in df.columns: c3.metric("JS Injected Schema", len(df[df["Schema in HTML"] == "JS Injected"]))
                if "Noindex Risk"   in df.columns: c4.metric("Noindex Risk",       len(df[df["Noindex Risk"]   == "YES"]))
                st.dataframe(df[available], use_container_width=True, height=400)

    with tab4:
        st.subheader("Hidden & Interactive Elements")
        if not use_js:
            st.warning("Enable **JavaScript Rendering** for hidden content analysis.")
        else:
            hidden_cols = ["URL", "Dropdown Links", "Accordions/FAQ"]
            available_h = [c for c in hidden_cols if c in df.columns]
            if available_h:
                h1, h2 = st.columns(2)
                if "Dropdown Links" in df.columns: h1.metric("Pages with dropdowns",  len(df[df["Dropdown Links"] > 0]))
                if "Accordions/FAQ" in df.columns: h2.metric("Pages with accordions", len(df[df["Accordions/FAQ"] > 0]))
                st.info("""
                **Why does this matter?**
                - Dropdowns = navigation links Google may never crawl
                - Accordions/FAQ = hidden text indexed with lower weight by Google
                """)
                if "Dropdown Links" in df.columns:
                    st.dataframe(
                        df[available_h].sort_values("Dropdown Links", ascending=False),
                        use_container_width=True,
                        height=400,
                    )

    with tab5:
        st.subheader("Framework & GTM Analysis")
        if not use_js:
            st.warning("Enable **JavaScript Rendering** for framework and GTM analysis.")
        else:
            fw_cols      = ["URL", "Framework", "Rendering", "SEO Risk"]
            available_fw = [c for c in fw_cols if c in df.columns]
            if available_fw:
                st.subheader("Detected Frameworks")
                if "Framework" in df.columns:
                    fw_counts = df["Framework"].value_counts().reset_index()
                    fw_counts.columns = ["Framework", "Pages"]
                    fig_fw = px.bar(fw_counts, x="Framework", y="Pages",
                                    color="Framework", title="Framework per page", text="Pages")
                    fig_fw.update_traces(textposition="outside")
                    fig_fw.update_layout(showlegend=False, height=300)
                    st.plotly_chart(fig_fw, use_container_width=True)
                st.dataframe(df[available_fw], use_container_width=True, height=300)

            st.subheader("GTM Container Analysis")
            all_gtm = []
            for r in results:
                all_gtm.extend(r.get("gtm_analysis", []))

            if all_gtm:
                unique_gtm = {g["id"]: g for g in all_gtm}.values()
                for gtm in unique_gtm:
                    with st.expander(f"GTM Container: {gtm['id']}"):
                        col_g1, col_g2 = st.columns(2)
                        with col_g1:
                            st.markdown(f"**GA4 IDs:** {', '.join(gtm['ga4_ids']) or 'None found'}")
                            st.markdown(f"**Universal Analytics:** {', '.join(gtm['ua_ids']) or 'None (good)'}")
                            st.markdown(f"**Meta Pixel:** {'Yes' if gtm['has_meta_pixel'] else 'No'}")
                            st.markdown(f"**Google Ads:** {', '.join(gtm['google_ads_ids']) or 'None'}")
                        with col_g2:
                            st.markdown(f"**A/B Testing tools:** {', '.join(gtm['ab_tools']) or 'None'}")
                            st.markdown(f"**Chat tools:** {', '.join(gtm['chat_tools']) or 'None'}")
                            st.markdown(f"**Duplicate GA4:** {'YES - Data error!' if gtm['duplicate_ga4'] else 'No'}")
                        if gtm["warnings"]:
                            for w in gtm["warnings"]:
                                st.warning(w)
            else:
                st.info("No GTM container found.")

    with tab6:
        st.subheader("Raw Data")
        t1, t2, t3 = st.tabs(["Pages", "Vendors", "Recommendations"])
        with t1:
            st.dataframe(df, use_container_width=True, height=420)
        with t2:
            if df_vendors.empty:
                st.info("No vendors found.")
            else:
                st.dataframe(df_vendors, use_container_width=True, height=420)
        with t3:
            if df_recs.empty:
                st.info("No recommendations.")
            else:
                st.dataframe(df_recs, use_container_width=True, height=420)

    st.divider()
    st.subheader("Export Report")
    excel = export_to_excel(df, df_vendors, df_recs)
    st.download_button(
        label="Download Excel Report (.xlsx)",
        data=excel,
        file_name="seo_js_audit.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )
    st.caption("Excel contains 3 sheets: JS Audit Summary, Vendor Analysis, Recommendations")
