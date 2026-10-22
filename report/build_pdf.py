"""Build the submission PDF from report/report.md.

    python report/build_pdf.py
    python report/build_pdf.py --browser "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

Steps: Markdown -> HTML (python-markdown), add a cover page, a contents list
and numbered figure captions, and style it for A4 print. Then a headless
Chromium browser (Brave or Chrome, found in /Applications) loads the page
over the DevTools protocol, waits for fonts and images, and prints it to
report/Smart_Delivery_Network_Report.pdf with page numbers and PDF bookmarks.
The browser runs with a throwaway profile and is closed when done.
(Brave's plain --print-to-pdf command-line mode hangs, hence the DevTools route.)

Needs: pip install markdown (pdfplumber, optional, for the page count check).
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
import json
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import markdown

from take_screenshots import Tab  # DevTools helper shared with the screenshot script

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "report.md"
OUT = HERE / "Smart_Delivery_Network_Report.pdf"
BROWSERS = [
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]

TITLE = "Smart Delivery Network"
TITLE_2 = "on Kalyani"
SUBTITLE = ("Computational geometry and approximation algorithms for delivery planning "
            "on real OpenStreetMap data, on both banks of the Hooghly")
COURSE = "Algorithms II (CSC711) · Mini Project Report"
TEAM = [("Akash Chakraborty", "1059", "CSE/23011"),
        ("Anipriyo Mandal", "1065", "CSE/23017"),
        ("Arpan Mandal", "1075", "CSE/23027")]
REPO = "https://github.com/anipriyo/smart-delivery-network"
ALGOS = [("Voronoi", "#E11D48"), ("KD-tree", "#059669"), ("Closest pair", "#7C3AED"),
         ("Convex hull", "#D97706"), ("Set cover", "#0891B2"), ("River check", "#2563EB")]

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');
@page { size: A4; margin: 19mm 17mm 18mm 17mm;
        @top-right { content: "Smart Delivery Network on Kalyani"; font: 600 7.5pt Inter, sans-serif; color: #94A3B8; }
        @top-left { content: "Algorithms II · Mini Project"; font: 600 7.5pt Inter, sans-serif; color: #94A3B8; }
        @bottom-center { content: counter(page) " / " counter(pages); font: 600 8pt Inter, sans-serif; color: #64748B; } }
@page :first { margin: 0; @top-right { content: none; } @top-left { content: none; } @bottom-center { content: none; } }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font-family: Inter, -apple-system, "Helvetica Neue", Arial, sans-serif; font-size: 9.6pt; line-height: 1.55;
       color: #0F172A; margin: 0; font-feature-settings: "cv11", "ss01"; }

/* ---------- cover ---------- */
.cover { height: 297mm; width: 210mm; position: relative; overflow: hidden; break-after: page; background: #FFFFFF; }
.cover .band { background: #1E1B4B; color: #fff; padding: 22mm 20mm 16mm; position: relative; }
.cover .band::after { content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 2.2mm;
                      background: linear-gradient(90deg, #E11D48 0 16.6%, #D97706 16.6% 33.3%, #059669 33.3% 50%,
                                                  #7C3AED 50% 66.6%, #0891B2 66.6% 83.3%, #2563EB 83.3%); }
.cover .eyebrow { font-size: 9pt; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: #C7D2FE; }
.cover h1 { font-size: 38pt; line-height: 1.04; font-weight: 800; letter-spacing: -0.035em; margin: 7mm 0 0; color: #fff; border: 0; padding: 0; }
.cover h1 span { color: #A5B4FC; }
.cover .sub { font-size: 12pt; line-height: 1.5; color: #E0E7FF; max-width: 150mm; margin-top: 6mm; }
.cover .algos { display: flex; flex-wrap: wrap; gap: 2.5mm; margin-top: 8mm; }
.cover .algos span { font-size: 8.5pt; font-weight: 700; color: #fff; padding: 1.4mm 3.4mm; border-radius: 2mm;
                     background: rgba(255,255,255,.10); border: 1px solid rgba(255,255,255,.22); }
.cover .algos i { display: inline-block; width: 2.2mm; height: 2.2mm; border-radius: .5mm; margin-right: 1.8mm; vertical-align: 0.1mm; }
.cover .hero { margin: 10mm 20mm 0; height: 92mm; border-radius: 3mm; overflow: hidden; border: 1px solid #E2E8F0;
               box-shadow: 0 2mm 6mm rgba(15,23,42,.10); }
.cover .hero img { width: 100%; height: 100%; object-fit: cover; object-position: 50% 62%; display: block; }
.cover .meta { margin: 10mm 20mm 0; display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4mm; }
.cover .person { border: 1px solid #E2E8F0; border-radius: 2.5mm; padding: 3.5mm 4mm; border-top: 1mm solid #4F46E5; }
.cover .person b { display: block; font-size: 11pt; font-weight: 700; }
.cover .person span { display: block; font-size: 8.5pt; color: #64748B; margin-top: .8mm; }
.cover .foot { position: absolute; left: 20mm; right: 20mm; bottom: 16mm; display: flex; justify-content: space-between;
               align-items: flex-end; font-size: 8.8pt; color: #475569; border-top: 1px solid #E2E8F0; padding-top: 4mm; }
.cover .foot b { color: #0F172A; display: block; font-size: 8pt; text-transform: uppercase; letter-spacing: .1em; margin-bottom: 1mm; }
.cover .foot a { color: #4338CA; text-decoration: none; font-weight: 600; }

/* ---------- contents ---------- */
.toc { break-after: page; }
.toc h2 { margin-top: 0; }
.toc ol { list-style: none; padding: 0; margin: 4mm 0 0; counter-reset: none; }
.toc li { display: flex; gap: 4mm; padding: 2.6mm 0; border-bottom: 1px solid #EEF2F6; font-size: 10.5pt; font-weight: 600; }
.toc li .n { color: #4F46E5; width: 10mm; flex: none; font-weight: 800; }
.toc .abstract { margin-top: 10mm; padding: 5mm 6mm; background: #F8FAFC; border: 1px solid #E2E8F0; border-left: 1.2mm solid #4F46E5;
                 border-radius: 2mm; font-size: 9.6pt; color: #334155; }
.toc .abstract b { color: #0F172A; }

/* ---------- body ---------- */
h2 { font-size: 15pt; font-weight: 800; letter-spacing: -0.02em; margin: 9mm 0 3mm; padding-bottom: 2mm; border-bottom: 1.4px solid #E2E8F0;
     break-after: avoid; color: #1E1B4B; }
h2.new-page { break-before: page; margin-top: 0; }
h3 { font-size: 11.5pt; font-weight: 700; margin: 6mm 0 2mm; break-after: avoid; color: #0F172A; }
p { margin: 0 0 2.6mm; }
ul, ol { margin: 0 0 3mm; padding-left: 5.5mm; }
li { margin-bottom: 1mm; }
li > ul { margin-top: 1mm; margin-bottom: 1mm; }
strong { font-weight: 700; color: #0F172A; }
a { color: #4338CA; text-decoration: none; }
code { font-family: "JetBrains Mono", Menlo, monospace; font-size: 8.4pt; background: #F1F5F9; border-radius: 1mm; padding: .2mm 1mm; color: #1E293B; }
pre { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 2mm; padding: 3mm 4mm; break-inside: avoid; overflow: hidden; }
pre code { background: none; padding: 0; font-size: 8.4pt; line-height: 1.5; white-space: pre-wrap; }
hr { display: none; }
table { width: 100%; border-collapse: collapse; margin: 2mm 0 4mm; font-size: 8.4pt; line-height: 1.42; break-inside: auto; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
th { background: #EEF2FF; color: #1E1B4B; font-weight: 700; text-align: left; padding: 1.8mm 2.2mm; border-bottom: 1.2px solid #C7D2FE; }
td { padding: 1.7mm 2.2mm; border-bottom: 1px solid #E2E8F0; vertical-align: top; }
tbody tr:nth-child(even) td { background: #F8FAFC; }
figure { margin: 3mm 0 5mm; break-inside: avoid; }
figure img { width: 100%; border: 1px solid #E2E8F0; border-radius: 2mm; display: block; }
figcaption { font-size: 8.2pt; color: #475569; line-height: 1.45; margin-top: 2mm; }
figcaption b { color: #1E1B4B; }
"""


def split_title_block(md: str) -> str:
    """Drop the title block (everything before the first '## ' heading)."""
    i = md.find("\n## ")
    return md[i + 1:] if i >= 0 else md


LIST_ITEM = re.compile(r"^\s*(?:[-*]|\d+\.)\s")


def normalise_lists(md: str) -> str:
    """Adapt CommonMark-style lists to Python-Markdown's stricter rules.

    Python-Markdown needs nested content indented by multiples of 4 spaces and
    a blank line between an intro sentence and the list that follows it; the
    report uses 2-3 space indents and "...:" intros directly followed by items.
    """
    out: list[str] = []
    fenced = False
    item_has_blocks = False  # the current top-level item already holds a blank-separated block
    for line in md.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if not fenced:
            n = len(line) - len(line.lstrip(" "))
            if line.strip() and n % 4:
                line = " " * ((n + 3) // 4 * 4) + line.lstrip(" ")
            prev = out[-1] if out else ""
            if LIST_ITEM.match(line) and prev.strip():
                intro = prev.rstrip().endswith(":") and not LIST_ITEM.match(prev)
                next_top_item = not line.startswith(" ") and (item_has_blocks or prev.startswith(" "))
                if intro or next_top_item:
                    out.append("")
            if not line.strip():
                item_has_blocks = True
            elif LIST_ITEM.match(line) and not line.startswith(" "):
                item_has_blocks = False
            elif not line.startswith(" "):
                item_has_blocks = False  # back to plain paragraphs
        out.append(line)
    return "\n".join(out) + "\n"


def figures(md: str) -> str:
    """Turn '### Screenshot: Title' + image into a numbered figure."""
    n = 0

    def repl(m: re.Match) -> str:
        nonlocal n
        n += 1
        title, alt, src = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        return (f'<figure><img src="{html.escape(src)}" alt="">'
                f'<figcaption><b>Figure {n}. {html.escape(title)}.</b> {html.escape(alt)}</figcaption></figure>\n')

    return re.sub(r"### Screenshot: ([^\n]+)\n\s*!\[([^\]]*)\]\(([^)]+)\)\n", repl, md)


def contents(md: str) -> list[tuple[str, str]]:
    items = []
    for line in md.splitlines():
        if line.startswith("## "):
            text = line[3:].strip()
            m = re.match(r"(\d+)\.\s+(.*)", text)
            a = re.match(r"Appendix ([A-Z])\.\s+(.*)", text)
            if m:
                items.append((m.group(1), m.group(2)))
            elif a:
                items.append((a.group(1), f"Appendix: {a.group(2)}"))
            else:
                items.append(("", text))
    return items


def cover(today: str) -> str:
    algos = "".join(f'<span><i style="background:{c}"></i>{html.escape(a)}</span>' for a, c in ALGOS)
    people = "".join(f'<div class="person"><b>{html.escape(n)}</b><span>Reg. {r} · Roll {roll}</span></div>'
                     for n, r, roll in TEAM)
    return f"""<section class="cover">
  <div class="band">
    <div class="eyebrow">{html.escape(COURSE)}</div>
    <h1>{html.escape(TITLE)}<br><span>{html.escape(TITLE_2)}</span></h1>
    <div class="sub">{html.escape(SUBTITLE)}</div>
    <div class="algos">{algos}</div>
  </div>
  <div class="hero"><img src="screenshots/network_map.png" alt=""></div>
  <div class="meta">{people}</div>
  <div class="foot">
    <div><b>Source code</b><a href="{REPO}">{REPO.replace("https://", "")}</a></div>
    <div style="text-align:right"><b>Date</b>{html.escape(today)}</div>
  </div>
</section>"""


def toc(items: list[tuple[str, str]]) -> str:
    rows = "".join(f'<li><span class="n">{html.escape(n)}</span><span>{html.escape(t)}</span></li>' for n, t in items)
    return f"""<section class="toc"><h2>Contents</h2><ol>{rows}</ol>
<div class="abstract"><b>Summary.</b> A delivery network around Kalyani, West Bengal, built from 571 real
OpenStreetMap places in a 401 km² area on both banks of the Hooghly. Five Algorithms II techniques plan it:
Voronoi zones (who serves whom), a KD-tree (what is where), divide-and-conquer closest pair (what is near),
the convex hull (how far it reaches) and greedy set cover (which sites to keep), shown in an interactive
Streamlit dashboard with step-by-step walkthroughs. A river check then measures where straight-line
planning breaks: with one road bridge along 27.5 km of river, a van's real trip to a cross-river hub is
more than twice the straight line.</div></section>"""


def build_html(today: str) -> str:
    md = SOURCE.read_text(encoding="utf-8")
    body_md = figures(normalise_lists(split_title_block(md)))
    items = contents(body_md)
    body = markdown.markdown(body_md, extensions=["tables", "fenced_code", "sane_lists", "attr_list"])
    # Start the main sections that open a new topic on a fresh page.
    for heading in ("1. Problem Statement", "3. Algorithms Used", "6. Worked Example", "7. Real-World Issue",
                    "Appendix A."):
        body = re.sub(rf"<h2>({re.escape(heading)}[^<]*)</h2>", r'<h2 class="new-page">\1</h2>', body, count=1)
    base = HERE.as_uri() + "/"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><base href="{base}">
<title>{html.escape(TITLE)} {html.escape(TITLE_2)}</title><style>{CSS}</style></head>
<body>{cover(today)}{toc(items)}<main>{body}</main></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--browser", default=next((b for b in BROWSERS if Path(b).exists()), None))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--keep-html", action="store_true", help="also write report/report_print.html")
    ap.add_argument("--port", type=int, default=9334, help="DevTools port for the headless browser")
    args = ap.parse_args()
    if not args.browser:
        raise SystemExit("No Chromium-based browser found; pass --browser /path/to/chrome")

    today = dt.date.today().strftime("%-d %B %Y")
    page = build_html(today)
    work = Path(tempfile.mkdtemp(prefix="sdn_pdf_"))
    src = work / "report.html"
    src.write_text(page, encoding="utf-8")
    if args.keep_html:
        (HERE / "report_print.html").write_text(page, encoding="utf-8")
    proc = subprocess.Popen(
        [args.browser, "--headless=new", f"--remote-debugging-port={args.port}", "--remote-allow-origins=*",
         f"--user-data-dir={work / 'profile'}", "--no-first-run", "--no-default-browser-check",
         "--allow-file-access-from-files", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(60):
            try:
                targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{args.port}/json/list"))
                pages = [t for t in targets if t.get("type") == "page"]
                if pages:
                    break
            except OSError:
                pass
            time.sleep(0.5)
        else:
            raise SystemExit("headless browser did not start")
        tab = Tab(pages[0]["webSocketDebuggerUrl"])
        tab.call("Page.enable")
        tab.call("Page.navigate", url=src.as_uri())
        for _ in range(120):  # wait for the document, web fonts and every image
            ready = tab.js("(async () => { if (document.readyState !== 'complete') return false;"
                           " await document.fonts.ready;"
                           " return [...document.images].every(i => i.complete && i.naturalWidth > 0); })()")
            if ready:
                break
            time.sleep(0.5)
        time.sleep(1.0)
        params = dict(printBackground=True, preferCSSPageSize=True, displayHeaderFooter=False)
        try:
            result = tab.call("Page.printToPDF", generateDocumentOutline=True, **params)
        except RuntimeError:  # older browsers: no PDF bookmarks
            result = tab.call("Page.printToPDF", **params)
        Path(args.out).write_bytes(base64.b64decode(result["data"]))
        tab.ws.close()
    finally:
        proc.terminate()  # only the browser this script started
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(work, ignore_errors=True)
    try:
        import pdfplumber
        with pdfplumber.open(args.out) as pdf:
            print(f"Wrote {args.out} ({len(pdf.pages)} pages)")
    except ImportError:
        print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
