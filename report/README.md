# report/

The written project report and what it needs.

| File | What it is | How it is produced |
|---|---|---|
| `report.md` | The report for the Kalyani region version of the dashboard (both banks of the Hooghly; rewritten 22 Oct 2026) | Written by hand. The numbers in §2, §6 and §7 come from `worked_example.py`. |
| `worked_example.py` | Prints every number used in the report: region facts and the projection check (§2), the worked example (§6) and the river check by van and by two-wheeler (§7). Uses the app's defaults: seed 42, 5 warehouses, 80 customers, a 3.0 × 2.4 km search area around Kalyani City, and a 4 km radius. Keep these in step with `ui/state.py` and `ui/pages.py`. | `~/.venvs/analysis/bin/python report/worked_example.py` |
| `screenshots/*.png` | Network map, River crossing (van mode), Coverage planner and Walkthrough (KD-tree search, final step), 1440 px wide, default settings | `take_screenshots.py` (below) |
| `take_screenshots.py` | Opens the running app in a headless Brave/Chrome with a throwaway profile, takes the four screenshots, closes the browser | see below |
| `Smart_Delivery_Network_Report.pdf` | **Out of date**: the PDF of the original synthetic-plane report. Its metadata says it was made with the ReportLab PDF library, but the script that made it was not kept. | Not reproducible yet (see below) |

## Commands (from the project root)

Numbers for §2, §6 and §7:

```bash
~/.venvs/analysis/bin/python report/worked_example.py
```

Screenshots: start the app with its default settings, then run the script in
a second terminal. It needs internet for the CARTO basemap tiles.

```bash
~/.venvs/analysis/bin/streamlit run app.py
```

```bash
~/.venvs/analysis/bin/python report/take_screenshots.py
```

Options: `--url` (default `http://localhost:8501`) and `--browser` (path to a
Chromium-based browser; Brave or Chrome in `/Applications` is found
automatically).

## PDF

No Markdown-to-PDF tool is installed on the project Mac (no pandoc, LaTeX,
weasyprint, wkhtmltopdf or typst, and no reportlab or markdown package in
`~/.venvs/analysis`), so the PDF has not been regenerated for the new report.
Whoever regenerates it should save the command or script here. The report
uses Unicode symbols (δ, √, ≈, ², ₀, ↔), so the tool needs a Unicode-aware
PDF engine (for pandoc, e.g. xelatex rather than pdflatex). Image links are
relative to `report/`.
