## 📘 `README.md`````markdown
# 🔎 JavaScript Element Auditor

A Streamlit app for SEO consultants to perform a full JavaScript audit
across an entire website — via sitemap or root domain crawl.

---

## Features

| Feature | Details |
|---|---|
| 🗺️ Sitemap crawl | Parses XML sitemaps, including nested sitemap indexes |
| 🌱 Root domain crawl | BFS crawl — follows all internal links, no URL cap |
| ⚙️ Static mode | Fast audit using `requests` + `BeautifulSoup` |
| 🎭 JS Rendering mode | Full headless browser audit via `Playwright` (Chromium) |
| 📸 Screenshot | Captures a sample screenshot of the first audited page |
| 📊 Charts | Bar chart (element types), pie chart (1st vs 3rd party), per-page stacked bar |
| 📥 Excel export | Two-sheet report: page summary + all script sources |

---

## Audited JS Elements (per page)

- `<script>` tag total count
- External scripts (with `src` attribute)
- Inline scripts (no `src`)
- `async` scripts
- `defer` scripts
- `type="module"` scripts
- 1st party vs 3rd party external scripts
- Inline JS total character count
- Full list of all external script source URLs

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/js-auditor.git
cd js-auditor```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt```

### 3. Install Playwright browser (required for JS Rendering mode)

```bash
playwright install chromium```

---

## Running the App

```bash
streamlit run app.py```

Open your browser at `http://localhost:8501`

---

## Usage

1. Paste a **Sitemap URL** (e.g. `https://example.com/sitemap.xml`)
   or a **Root URL** (e.g. `https://example.com`) into the input box.
2. The app auto-detects which mode to use — or you can override it.
3. In the **sidebar**, choose:
   - **Static Mode** (default) — fast, no JS rendering
   - **JS Rendering** — Playwright headless browser, slower but accurate for SPAs
   - **Screenshot** toggle — captures the first page visually
4. Click **🚀 Start Full Audit**
5. Watch live progress, then review charts, tables, and download the Excel report.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `playwright._impl._errors` | Run `playwright install chromium` |
| Streamlit freezes on large sites | This is normal — crawling takes time with no URL cap |
| Sitemap not parsed | Ensure the URL returns valid XML; try overriding to "Sitemap" mode |
| Screenshot not available | Enable JS Rendering in the sidebar |

---

## Project Structure

```js-auditor/
├── app.py            ← Streamlit frontend and UI
├── backend.py        ← Crawling, auditing, data processing, export
├── requirements.txt  ← Python dependencies
└── README.md         ← This file```

---

## Tech Stack

- [Streamlit](https://streamlit.io) — UI framework
- [Playwright](https://playwright.dev/python/) — Headless browser / JS rendering
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) — HTML parsing
- [Requests](https://docs.python-requests.org/) — HTTP client
- [Pandas](https://pandas.pydata.org/) — Data processing
- [Plotly](https://plotly.com/python/) — Interactive charts
- [OpenPyXL](https://openpyxl.readthedocs.io/) — Excel export
