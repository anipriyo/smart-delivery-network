# report/

The written project report and what it needs.

| File | What it is | How it is produced |
|---|---|---|
| `report.md` | The report for the Kalyani region version of the dashboard (both banks of the Hooghly; rewritten 22 Oct 2026) | Written by hand. The numbers in §2, §6 and §7 come from `worked_example.py`. |
| `worked_example.py` | Prints every number used in the report: region facts and the projection check (§2), the worked example (§6) and the river check by van and by two-wheeler (§7). Uses the app's defaults: seed 42, 5 warehouses, 80 customers, a 3.0 × 2.4 km search area around Kalyani City, and a 4 km radius. Keep these in step with `ui/state.py` and `ui/pages.py`. | `~/.venvs/analysis/bin/python report/worked_example.py` |
| `screenshots/*.png` | Network map, River crossing (van mode), Coverage planner and Walkthrough (KD-tree search, final step), 1440 px wide, default settings, plus `map_closeup.png` (just the map at 2× resolution, used on the PDF cover and in the README) | `take_screenshots.py` (below) |
| `take_screenshots.py` | Opens the running app in a headless Brave/Chrome with a throwaway profile, takes the four screenshots, closes the browser | see below |
| `Smart_Delivery_Network_Report.pdf` | **The submission PDF** (20 pages, A4): cover with course, team and repository link, contents, the report with numbered figures, page numbers and PDF bookmarks | `build_pdf.py` (below) |
| `build_pdf.py` | Markdown → styled HTML (cover, contents, figure captions, print CSS) → PDF, printed by a headless Brave/Chrome over the DevTools protocol with a throwaway profile | see below |

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

Rebuild after any change to `report.md` or the screenshots:

```bash
~/.venvs/analysis/bin/python report/build_pdf.py
```

Needs the `markdown` package (`pip install markdown`; installed in
`~/.venvs/analysis` on 22 Oct 2026) and Brave or Chrome in `/Applications`
(`--browser` to choose another). The cover's team, course and repository URL
are constants at the top of `build_pdf.py`; everything else comes from
`report.md`, whose title block (before §1) is replaced by the cover. Brave's
plain `--print-to-pdf` command-line mode hangs, which is why the script prints
over the DevTools protocol instead. `--keep-html` also writes the intermediate
HTML to `report/report_print.html` for inspection.
