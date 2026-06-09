from pathlib import Path
import html
import re

ROOT = Path(__file__).resolve().parents[1]
WITNESS_SOURCE = ROOT / "data" / "witness_files" / "WABAW"
OUTPUT = ROOT / "witnesses" / "WABAW.qmd"

REPORT_START_RE = re.compile(r"#\s+@([A-Z]{4,5}V\d+P\d+[A-Z]*)_BEG_([A-Z]{4,5})")
REPORT_END_RE = re.compile(r"@([A-Z]{4,5}V\d+P\d+[A-Z]*)_END_([A-Z]{4,5})")
PAGE_RE = re.compile(r"PageV0*(\d+)P0*(\d+)[A-Z]*")
COMMENT_RE = re.compile(r"#\s+@COMMENT:\s*(.*)", re.DOTALL)
EC_TAG_RE = re.compile(r"\s*@EC_[\d/]+@")

QURAN_RE = re.compile(
    r"@QURS(\d+)A(\d+)_BEG\s*(.*?)\s*@QURS\1A(\d+)_END",
    re.DOTALL,
)

TAG_RE = re.compile(r"@TR\w+@|@EW\w+@")
VAR_RE = re.compile(r"\bVAR_([A-Z]{4,5}V\d+P\d+[A-Z]*)\b")


def strip_metadata(text: str) -> tuple[str, str]:
    arabic_title = "السيرة النبوية"
    transliterated_name = "WABAW"

    match = re.search(r"#META# الكتاب:\s*(.+)", text)
    if match:
        arabic_title = match.group(1).strip()

    match = re.search(r"#META# Transliterated Name:\s*(.+)", text)
    if match:
        transliterated_name = match.group(1).strip()

    body = re.sub(r"#OpenITI-RKJ#\s*", "", text)
    body = re.sub(r"#META#.*\n?", "", body)

    return body.strip(), arabic_title, transliterated_name


def format_quran(text: str) -> str:
    def repl(match):
        sura = match.group(1).lstrip("0") or "0"
        start_aya = match.group(2).lstrip("0") or "0"
        quran_text = html.escape(match.group(3).strip())
        href = f"https://quran.com/{sura}/{start_aya}"
        return f'<a href="{href}" class="quran">{quran_text}</a>'

    return QURAN_RE.sub(repl, text)


def format_pages(text: str) -> str:
    def repl(match):
        vol = match.group(1).lstrip("0") or "0"
        page = match.group(2).lstrip("0") or "0"
        return f'<span class="page-no" title="volume {vol} page {page}">§</span>'

    return PAGE_RE.sub(repl, text)


def clean_report_text(text: str) -> str:
    text = EC_TAG_RE.sub("", text)
    text = REPORT_START_RE.sub("", text)
    text = REPORT_END_RE.sub("", text)
    text = VAR_RE.sub(r'<span class="variant-id">VAR_\1</span>', text)
    text = TAG_RE.sub("", text)
    text = html.escape(text)

    # Restore safe HTML inserted before escaping where needed.
    text = text.replace("&lt;span class=&quot;variant-id&quot;&gt;", '<span class="variant-id">')
    text = text.replace("&lt;/span&gt;", "</span>")

    text = format_pages(text)
    text = format_quran(text)

    return " ".join(text.split())


def split_comment(block: str) -> tuple[str, str]:
    """
    Split one witness report block into report text and editorial comment.

    Comments in the source look like:

        # @COMMENT: A similar fragment is also found...
    """
    parts = re.split(r"\n#\s*@COMMENT:\s*", block, maxsplit=1)

    if len(parts) == 1:
        return block, ""

    report_text = parts[0].strip()
    comment = parts[1].strip()

    # Remove internal editor/date tags such as @EC_03/09/23@
    comment = EC_TAG_RE.sub("", comment).strip()

    return report_text, comment


def parse_reports(text: str) -> list[dict]:
    """
    Parse witness reports and attach comments to the preceding report.

    We split only on report-start tags like:

        # @SHBMV02P036H_BEG_WABAW

    This keeps the following PageV... line and optional # @COMMENT line
    attached to the same report.
    """
    chunks = re.split(r"\n(?=#\s+@[A-Z]{4,5}V\d+P\d+[A-Z]*_BEG_[A-Z]{4,5})", text)

    reports = []

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        start_match = REPORT_START_RE.search(chunk)
        if not start_match:
            continue

        report_id = start_match.group(1)
        report_text, comment = split_comment(chunk)

        reports.append(
            {
                "id": report_id,
                "html": clean_report_text(report_text),
                "comment": html.escape(comment),
            }
        )

    return reports

def clean_footnote_text(text: str) -> str:
    """
    Clean comment text for use in a Quarto/Pandoc footnote definition.
    """
    text = EC_TAG_RE.sub("", text)
    text = " ".join(text.split())

    # Prevent accidental Markdown footnote/bracket parsing inside comments.
    text = text.replace("[", r"\[")
    text = text.replace("]", r"\]")

    return text


def build_qmd() -> None:
    source = WITNESS_SOURCE.read_text(encoding="utf-8")
    body, arabic_title, witness_title = strip_metadata(source)
    reports = parse_reports(body)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    qmd_parts = [
        "---",
        f'title: "{witness_title}"',
        "---",
        "",
        f"# {arabic_title}",
        "",
        "**Witness code:** `WABAW`",
        "",
        "This page is generated from the encoded Sira witness source file.",
        "",
        "```{=html}",
        '<div class="sira-witness" data-witness="WABAW">',
        "```",
        "",
    ]

    footnotes = []

    for report in reports[:50]:
        report_id = report["id"]

        qmd_parts.append(
            f'''```{{=html}}
<article class="sira-report" id="{report_id}" dir="rtl">
  <header class="sira-report-header">
    <a class="report-id" href="#{report_id}">{report_id}</a>
  </header>
  <div class="witness-text">
    {report["html"]}
  </div>
</article>
```'''
        )

        if report["comment"]:
            footnote_id = f"comment-{report_id}"
            comment_text = clean_footnote_text(report["comment"])

            qmd_parts.extend(
                [
                    "",
                    '::: {.sira-comment-ref}',
                    f"Comment.[^{footnote_id}]",
                    ":::",
                    "",
                ]
            )

            footnotes.append(f"[^{footnote_id}]: {comment_text}")

    qmd_parts.extend(
        [
            "```{=html}",
            "</div>",
            "```",
            "",
        ]
    )

    if footnotes:
        qmd_parts.extend(
            [
                "",
                *footnotes,
                "",
            ]
        )

    OUTPUT.write_text("\n".join(qmd_parts), encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    print(f"Parsed {len(reports)} reports; wrote first 50.")
    print(f"Wrote {len(footnotes)} editorial comments as Quarto footnotes.")


if __name__ == "__main__":
    build_qmd()