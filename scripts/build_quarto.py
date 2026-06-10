from pathlib import Path
import csv
import html
import re

ROOT = Path(__file__).resolve().parents[1]
WITNESS_DIR = ROOT / "data" / "witness_files"
OUTPUT_DIR = ROOT / "witnesses"
QUARTO_YML = ROOT / "_quarto.yml"

STATIC_CHAPTERS = [
    "index.qmd",
    "maps.qmd",
    "witnesses/index.qmd",
]

WITNESS_META = ROOT / "data" / "meta" / "Witness_list_sheet.csv"
BIBLIOGRAPHY_META = ROOT / "data" / "meta" / "Kevin Bibliography.csv"

PAGE_SYMBOL = "§"

# Set to an integer for local testing, e.g. 50.
# Keep as None for publication builds.
GROUP_LIMIT: int | None = None

# Comments longer than this are rendered as collapsible editorial notes
# instead of margin footnotes.
LONG_COMMENT_CHAR_LIMIT = 1200

REPORT_START_RE = re.compile(r"#\s+@([A-Z]{4,5}V\d+P\d+[A-Z]*)_BEG_([A-Z]{4,5})")
REPORT_END_RE = re.compile(r"@([A-Z]{4,5}V\d+P\d+[A-Z]*)_END_([A-Z]{4,5})")
REPORT_ID_RE = re.compile(r"([A-Z]{4,5})V0*(\d+)P0*(\d+)([A-Z]*)")
PAGE_RE = re.compile(r"PageV0*(\d+)P0*(\d+)[A-Z]*")
MALFORMED_PAGE_RE = re.compile(r"\bPageV\d+P(?!\d)")
COMMENT_RE = re.compile(r"#\s+@COMMENT:\s*", re.IGNORECASE)
EC_TAG_RE = re.compile(r"\s*@EC_[\d/]+@")
SECTION_RE = re.compile(r"^###\s+(\|+)\s*(.+)$", re.MULTILINE)

QURAN_RE = re.compile(
    r"@QURS(\d+)A(\d+)_BEG\s*(.*?)\s*@QURS\1A(\d+)_END",
    re.DOTALL,
)

TAG_RE = re.compile(r"@(?:TR|EW)\w+@?")
VAR_RE = re.compile(r"\bVAR_([A-Z]{4,5}V\d+P\d+[A-Z]*)\b")


def strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)

def markdown_table_cell(value: object) -> str:
    """
    Escape text for use inside a Markdown table cell.
    """
    text = str(value or "").strip()
    text = text.replace("|", r"\|")
    text = re.sub(r"\s+", " ", text)
    return text

def escape_bibtex(value: str) -> str:
    """
    Escape a string for simple BibTeX field values.
    """
    value = str(value or "")
    value = value.replace("\\", "\\textbackslash{}")
    value = value.replace("{", "\\{")
    value = value.replace("}", "\\}")
    value = value.replace("&", "\\&")
    value = value.strip()
    return value


def slugify_filename(value: str) -> str:
    """
    Keep witness output filenames simple and predictable.
    """
    value = value.strip()
    value = re.sub(r"[^A-Za-z0-9_-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "UNKNOWN"

def read_csv_rows(path: Path) -> list[dict[str, str]]:
    """
    Read a CSV file with a small set of likely encodings.

    The witness CSV currently appears to be Windows-1252 encoded; UTF-8 is
    still tried first because that is the preferred export format.
    """
    encodings = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]

    last_error = None

    for encoding in encodings:
        try:
            with path.open(encoding=encoding, newline="") as file:
                reader = csv.DictReader(file)
                rows = []

                for row in reader:
                    cleaned = {
                        (key or "").strip(): (value or "").strip()
                        for key, value in row.items()
                        if key is not None and key.strip()
                    }
                    rows.append(cleaned)

                return rows

        except UnicodeDecodeError as exc:
            last_error = exc

    raise UnicodeDecodeError(
        "csv",
        b"",
        0,
        1,
        f"Could not decode {path} with expected encodings. Last error: {last_error}",
    )


def first_present(row: dict[str, str], keys: list[str], default: str = "") -> str:
    """
    Return the first non-empty value found for a list of possible column names.
    """
    for key in keys:
        value = row.get(key, "").strip()
        if value:
            return value

    return default


def clean_lost_arabic(value: str) -> str:
    """
    Avoid displaying columns whose Arabic text was lost during CSV export.

    If the CSV contains only question marks/spaces in the Arabic-name field,
    return an empty string.
    """
    stripped = value.strip()

    if stripped and set(stripped) <= {"?", " "}:
        return ""

    return stripped


def load_witness_records() -> dict[str, dict[str, object]]:
    """
    Load witness metadata from data/meta/Witness_list_sheet.csv.
    """
    if not WITNESS_META.exists():
        return {}

    try:
        rows = read_csv_rows(WITNESS_META)
    except Exception as exc:
        print(f"Could not read {WITNESS_META}: {exc}")
        return {}

    records = {}

    for row in rows:
        code = first_present(row, ["Witness ", "Witness"]).strip()

        # Real witness codes look like WABAW, WAAAY, WMAAI, etc.
        # This skips helper/header rows such as "Regex" and "Tag".
        if not re.fullmatch(r"W[A-Z]{4}", code):
            continue

        arabic_name = first_present(row, ["Arabic", "Arabic name Arabic", "عبد", "???"])
        arabic_name = clean_lost_arabic(arabic_name)

        records[code] = {
            "code": code,
            "name": first_present(row, ["Arabic name", "Name"], code),
            "arabic": arabic_name,
            "passages": first_present(row, ["# of Passages (as of last update)", "Passages"]),
            "words": first_present(row, ["# of Words (as of last update)", "Words"]),
            "formatted": first_present(row, ["Formatted"]),
            "organized_by_story": first_present(row, ["Organized by Story"]),
            "uploaded_to_github": first_present(row, ["Uploaded to Github", "Uploaded to GitHub"]),
            "last_updated": first_present(row, ["Last Date Updated", "Last Updated"]),
            "notes": first_present(row, ["Notes"]),
        }

    return records


def load_witness_dict() -> dict[str, str]:
    """
    Compatibility helper for comment expansion.

    Returns:
        {
            "WABAW": "ʿAbbād b. al-ʿAwwām ...",
            ...
        }
    """
    records = load_witness_records()
    return {
        code: record.get("name") or code
        for code, record in records.items()
    }


def load_bibliography_dict() -> dict[str, dict[str, str]]:
    """
    Load bibliography metadata from data/meta/Kevin Bibliography.csv.
    """
    if not BIBLIOGRAPHY_META.exists():
        return {}

    try:
        rows = read_csv_rows(BIBLIOGRAPHY_META)
    except Exception as exc:
        print(f"Could not read {BIBLIOGRAPHY_META}: {exc}")
        return {}

    bibliography_dict = {}

    for row in rows:
        key = first_present(row, ["ID"]).strip()

        if not re.fullmatch(r"[A-Z]{4,5}", key):
            continue

        author = html.escape(first_present(row, ["short_author"]))
        title = html.escape(first_present(row, ["short_title"]))
        citation = first_present(row, ["Citation"])
        uri = first_present(row, ["URI"])
        notes = first_present(row, ["Notes"])
        dod = first_present(row, ["DOD"])
        old_id = first_present(row, ["ID_old"])

        if author and title:
            ref_html = f"<span class='ref-author'>{author}</span>, <span class='ref-title'>{title}</span>"
        elif title:
            ref_html = f"<span class='ref-title'>{title}</span>"
        elif author:
            ref_html = f"<span class='ref-author'>{author}</span>"
        else:
            ref_html = html.escape(key)

        bibliography_dict[key] = {
            "id": key,
            "old_id": old_id,
            "html": ref_html,
            "plain": strip_tags(ref_html),
            "citation": citation,
            "uri": uri,
            "notes": notes,
            "dod": dod,
            "short_author": strip_tags(author),
            "short_title": strip_tags(title),
        }

    return bibliography_dict

def build_witness_index_qmd(witness_records: dict[str, dict[str, object]], witness_results: list[dict[str, object]]) -> None:
    """
    Generate witnesses/index.qmd from witness metadata and generated witness pages.
    """
    output_path = OUTPUT_DIR / "index.qmd"

    generated_codes = {
        str(result["witness_code"])
        for result in witness_results
    }

    rows = []

    for code, record in sorted(
        witness_records.items(),
        key=lambda item: str(item[1].get("name", item[0])).strip("ʿ"),
    ):
        name = markdown_table_cell(html.escape(str(record.get("name", code))))
        arabic = markdown_table_cell(html.escape(str(record.get("arabic", ""))))
        passages = markdown_table_cell(record.get("passages", ""))
        words = markdown_table_cell(record.get("words", ""))
        organized = markdown_table_cell(html.escape(str(record.get("organized_by_story", ""))))

        if code in generated_codes:
            code_cell = f"[`{code}`]({code}.qmd)"
        else:
            code_cell = f"`{code}`"

        rows.append(
            f'| {code_cell} | {name} | <span lang="ar" dir="rtl">{arabic}</span> | {passages} | {words} | {organized} |'
        )

    qmd = [
        "---",
        'title: "Witness Versions"',
        "---",
        "",
        "This list of witness versions is generated from `data/meta/Witness_list_sheet.csv`.",
            "",
            "| Witness | Name | Arabic | Passages | Words | Organized by Story |",
            "|---|---|---:|---:|---:|---|",
            *rows,
            "",
        ]

    output_path.write_text("\n".join(qmd), encoding="utf-8")
    print(f"Wrote {output_path}")

def build_references_qmd() -> None:
    """
    Generate the Quarto bibliography page.

    Quarto/Pandoc fills the refs div from references.bib.
    """
    output_path = ROOT / "references.qmd"

    qmd = [
        "---",
        'title: "Bibliography"',
        'lang: "en"',
        "---",
        "",
        "# Bibliography {.unnumbered}",
        "",
        "::: {#refs}",
        ":::",
        "",
    ]

    output_path.write_text("\n".join(qmd), encoding="utf-8")
    print(f"Wrote {output_path}")

def build_references_bib(bibliography_dict: dict[str, dict[str, str]]) -> None:
    """
    Generate references.bib from Kevin Bibliography.csv.

    These entries are conservative because the CSV stores full citation strings
    rather than fully parsed bibliographic fields. They support Quarto/Pandoc
    citations such as [@SHBM].
    """
    output_path = ROOT / "references.bib"

    entries = []

    for key, record in sorted(bibliography_dict.items()):
        author = escape_bibtex(record.get("short_author", ""))
        title = escape_bibtex(record.get("short_title", "") or key)
        citation = escape_bibtex(record.get("citation", ""))
        uri = escape_bibtex(record.get("uri", ""))
        notes = escape_bibtex(record.get("notes", ""))

        fields = [
            f"  title = {{{title}}}",
        ]

        if author:
            fields.append(f"  author = {{{author}}}")

        if citation:
            fields.append(f"  note = {{{citation}}}")

        if uri:
            fields.append(f"  url = {{{uri}}}")

        if notes:
            fields.append(f"  annote = {{{notes}}}")

        entry = "@misc{" + key + ",\n" + ",\n".join(fields) + "\n}"
        entries.append(entry)

    output_path.write_text("\n\n".join(entries) + "\n", encoding="utf-8")
    print(f"Wrote {output_path}")


def clean_source_text(text: str, filename: str = "") -> str:
    """
    Lightly normalize known inconsistencies in the witness source before parsing.
    """
    text = EC_TAG_RE.sub("", text)
    text = text.replace("\r", "")
    text = text.replace("\u200e", "")

    if "\\" in text:
        print(f"{filename}: contains backslashes; removing them for generated output.")
        text = text.replace("\\", "")

    # Normalize comment tags:
    #   # @ COMMENT
    #   # @COMENT
    #   # @NOTE
    #   # @Comment
    text = re.sub(
        r"\n+#\s*@\s*(?:COMM?ENT|NOTE)",
        "\n# @COMMENT",
        text,
        flags=re.IGNORECASE,
    )

    # If a page number has accidentally been placed after a comment,
    # move it back before the comment.
    text = re.sub(
        r"(_END_.+?\n)(#\s*@COMMENT.+?\n)(PageV\d+P\d+[A-Z]*)",
        r"\1\3\n\2",
        text,
        flags=re.DOTALL,
    )

    return text


def strip_metadata(text: str, fallback_code: str) -> tuple[str, str, str, str]:
    arabic_title = "السيرة النبوية"
    transliterated_name = fallback_code
    witness_code = fallback_code

    match = re.search(r"#META# الكتاب:\s*(.+)", text)
    if match:
        arabic_title = match.group(1).strip()

    match = re.search(r"#META# Transliterated Name:\s*(.+)", text)
    if match:
        transliterated_name = match.group(1).strip()

    match = re.search(r"#META# Tag Name:\s*(.+)", text)
    if match:
        witness_code = match.group(1).strip()

    body = re.sub(r"#OpenITI-RKJ#\s*", "", text)
    body = re.sub(r"#META#.*\n?", "", body)

    return body.strip(), arabic_title, transliterated_name, witness_code


def format_quran(text: str) -> str:
    """
    Format Qur'an tags after the surrounding text has already been HTML-escaped.
    """
    def repl(match):
        sura = match.group(1).lstrip("0") or "0"
        start_aya = match.group(2).lstrip("0") or "0"
        end_aya = match.group(4).lstrip("0") or start_aya
        quran_text = match.group(3).strip()
        href = f"https://quran.com/{sura}/{start_aya}"

        if end_aya == start_aya:
            title = f"Qurʾān {sura}.{start_aya}"
        else:
            title = f"Qurʾān {sura}.{start_aya}-{end_aya}"

        return f'<a href="{href}" class="quran" title="{title}" target="_blank">{quran_text}</a>'

    return QURAN_RE.sub(repl, text)


def format_pages(text: str) -> str:
    def repl(match):
        vol = match.group(1).lstrip("0") or "0"
        page = match.group(2).lstrip("0") or "0"
        return f'<span class="page-no" title="end of page {page} of vol. {vol}">{PAGE_SYMBOL}</span>'

    return PAGE_RE.sub(repl, text)


def format_poetry(text: str) -> str:
    return re.sub(
        r"\n(.+?) %~% (.+)",
        r"\n<span class='poetry-line'><span class='hemistich1'>\1</span> <span class='hemistich2'>\2</span></span>",
        text,
    )


def format_see_references(text: str, bibliography_dict: dict[str, dict[str, str]]) -> str:
    """
    Convert SEE_ references into lightweight editorial markers.
    """
    def repl(match):
        ref = match.group(1)
        id_match = REPORT_ID_RE.match(ref)

        if not id_match:
            return f'<span class="see-reference" title="See {html.escape(ref)}">*</span>'

        siglum = id_match.group(1)
        vol = id_match.group(2).lstrip("0") or "0"
        page = id_match.group(3).lstrip("0") or "0"
        source = bibliography_dict.get(siglum, {}).get("plain", siglum)
        title = html.escape(f"See {source}, vol. {vol} p. {page}")

        return f'<span class="see-reference" title="{title}">*</span>'

    return re.sub(
        r"SEE_([A-Z]{4,5}V\d+P\d+[A-Z]*(?: *to +\w+)?)",
        repl,
        text,
    )


def clean_report_text(text: str, bibliography_dict: dict[str, dict[str, str]]) -> str:
    text = EC_TAG_RE.sub("", text)
    text = REPORT_START_RE.sub("", text)
    text = REPORT_END_RE.sub("", text)
    text = TAG_RE.sub("", text)
    text = format_see_references(text, bibliography_dict)

    # Escape first, then reintroduce only the safe generated HTML that we control.
    text = html.escape(text)
    text = VAR_RE.sub(r'<span class="variant-id">VAR_\1</span>', text)

    # Restore safe SEE marker spans generated before escaping.
    text = text.replace("&lt;span class=&quot;see-reference&quot; title=&quot;", '<span class="see-reference" title="')
    text = text.replace("&quot;&gt;*&lt;/span&gt;", '">*</span>')

    text = format_pages(text)
    text = format_quran(text)
    text = format_poetry(text)

    return " ".join(text.split())


def split_comment(block: str) -> tuple[str, str]:
    """
    Split one report block into report text and editorial comment.

    If a comment appears after a block of multiple reports, this simple parser
    attaches it to the immediately preceding parsed report. Long or ambiguous
    comments should be flagged during review.
    """
    parts = re.split(r"\n#\s*@COMMENT:\s*", block, maxsplit=1, flags=re.IGNORECASE)

    if len(parts) == 1:
        return block, ""

    report_text = parts[0].strip()
    comment = parts[1].strip()
    comment = EC_TAG_RE.sub("", comment).strip()

    return report_text, comment


def get_variant_ids(report_html: str) -> list[str]:
    variants = re.findall(
        r'<span class="variant-id">VAR_([A-Z]{4,5}V\d+P\d+[A-Z]*)</span>',
        report_html,
    )

    return list(dict.fromkeys(variants))


def build_variant_groups(reports: list[dict]) -> list[list[str]]:
    known_ids = {report["id"] for report in reports}
    graph = {report["id"]: set() for report in reports}
    report_order = {report["id"]: index for index, report in enumerate(reports)}

    for report in reports:
        report_id = report["id"]

        for variant_id in get_variant_ids(report["html"]):
            if variant_id in known_ids:
                graph[report_id].add(variant_id)
                graph[variant_id].add(report_id)

    visited = set()
    groups = []

    for report in reports:
        start_id = report["id"]

        if start_id in visited:
            continue

        stack = [start_id]
        group = []

        while stack:
            current_id = stack.pop()

            if current_id in visited:
                continue

            visited.add(current_id)
            group.append(current_id)

            neighbors = sorted(
                graph[current_id],
                key=lambda rid: report_order[rid],
                reverse=True,
            )

            for neighbor in neighbors:
                if neighbor not in visited:
                    stack.append(neighbor)

        group.sort(key=lambda rid: report_order[rid])
        groups.append(group)

    return groups


def get_report_reference_html(
    report_id: str,
    raw_report_text: str,
    bibliography_dict: dict[str, dict[str, str]],
) -> str:
    match = REPORT_ID_RE.match(report_id)

    if not match:
        return ""

    siglum = match.group(1)
    vol = match.group(2).lstrip("0") or "0"
    first_page = match.group(3).lstrip("0") or "0"

    source = bibliography_dict.get(siglum)

    if source:
        source_html = source["html"]
        source_link = f'<a href="../references.html#ref-{siglum}" class="source-link">{source_html}</a>'
    else:
        source_link = html.escape(siglum)

    pages = PAGE_RE.findall(raw_report_text)

    if pages:
        last_page = pages[-1][1].lstrip("0") or first_page
    else:
        last_page = first_page

    if last_page != first_page:
        page_label = f"vol. {vol} pp. {first_page}-{last_page}"
    else:
        page_label = f"vol. {vol} p. {first_page}"

    return (
        '<div class="sira-source-line" lang="en" dir="ltr">'
        f'<span class="source-label">Source:</span> {source_link}, {page_label}'
        "</div>"
    )


def format_comment_for_note(
    comment: str,
    witness_dict: dict[str, str],
    bibliography_dict: dict[str, dict[str, str]],
) -> str:
    """
    Convert an editorial comment into safe inline HTML.

    This preserves useful semantic expansion while using Quarto notes/callouts
    instead of custom hover/click comment containers.
    """
    comment = COMMENT_RE.sub("", comment)
    comment = EC_TAG_RE.sub("", comment)
    comment = TAG_RE.sub("", comment)
    comment = html.escape(comment)

    def expand_witness(match):
        code = match.group(0)
        label = html.escape(witness_dict.get(code, code))
        return f'<a href="{code}.html" class="witness-link">{code}</a> ({label})'

    def expand_reference(match):
        ref = match.group(0)
        siglum = match.group(1)
        vol = match.group(2).lstrip("0") or "0"
        page = match.group(3).lstrip("0") or "0"
        source = bibliography_dict.get(siglum)

        if source:
            source_html = source["html"]
            return (
                f'<a href="../references.html#ref-{siglum}" class="source-ref">{ref}</a> '
                f'({source_html}, vol. {vol} p. {page})'
            )

        return ref

    comment = re.sub(r"\bW[A-Z]{4}\b", expand_witness, comment)
    comment = re.sub(r"([A-Z]{4,5})V(\d+)P(\d+)([A-Z]*)", expand_reference, comment)
    comment = format_quran(comment)

    # Basic markdown-ish italics in comments.
    comment = re.sub(r"\*(.+?)\*", r"<em>\1</em>", comment)

    return " ".join(comment.split())


def parse_reports(
    text: str,
    bibliography_dict: dict[str, dict[str, str]],
    witness_code: str,
    warnings: list[str],
) -> list[dict]:
    chunks = re.split(r"\n(?=#\s+@[A-Z]{4,5}V\d+P\d+[A-Z]*_BEG_[A-Z]{4,5})", text)

    reports = []

    for chunk in chunks:
        chunk = chunk.strip()

        if not chunk:
            continue

        start_match = REPORT_START_RE.search(chunk)

        if not start_match:
            if re.search(r"\b[A-Z]{4,5}V\d+P\d+[A-Z]*\b", chunk):
                warnings.append(
                    "Found passage-like text that is not wrapped in a standard # @..._BEG_... tag."
                )
            continue

        report_id = start_match.group(1)
        report_witness_code = start_match.group(2)

        if report_witness_code != witness_code:
            warnings.append(
                f"{report_id}: passage start witness suffix {report_witness_code} "
                f"does not match witness-version code {witness_code}."
            )

        duplicate_variants = [
            variant_id
            for variant_id in set(VAR_RE.findall(chunk))
            if VAR_RE.findall(chunk).count(variant_id) > 1
        ]

        if duplicate_variants:
            warnings.append(
                f"{report_id}: duplicate variant IDs: {', '.join(sorted(duplicate_variants))}."
            )

        if MALFORMED_PAGE_RE.search(chunk):
            warnings.append(f"{report_id}: possible malformed page marker.")

        report_text, comment = split_comment(chunk)

        reports.append(
            {
                "id": report_id,
                "raw": report_text,
                "html": clean_report_text(report_text, bibliography_dict),
                "comment": comment,
            }
        )

    return reports


def split_sections(body: str) -> list[dict]:
    """
    Split a witness body into generated sections.

    Returns:
        [
            {"title": None, "level": 0, "content": "..."},
            {"title": "...", "level": 1, "content": "..."},
            ...
        ]
    """
    matches = list(SECTION_RE.finditer(body))

    if not matches:
        return [{"title": None, "level": 0, "content": body}]

    sections = []

    preface = body[: matches[0].start()].strip()
    if preface:
        sections.append({"title": None, "level": 0, "content": preface})

    for index, match in enumerate(matches):
        pipes = match.group(1)
        title = match.group(2).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        content = body[start:end].strip()

        sections.append(
            {
                "title": title,
                "level": len(pipes),
                "content": content,
            }
        )

    return sections


def render_section_heading(section: dict) -> str:
    if not section["title"]:
        return ""

    # Keep section headings as real Quarto headings.
    # ### | becomes ##, ### || becomes ###, etc.
    heading_level = min(section["level"] + 1, 6)
    hashes = "#" * heading_level
    title = html.escape(section["title"])

    return f'{hashes} <span lang="ar" dir="rtl">{title}</span>\n'


def render_report_article(report: dict, bibliography_dict: dict[str, dict[str, str]], label: str = "Passage") -> str:
    report_id = report["id"]
    reference_html = get_report_reference_html(report_id, report["raw"], bibliography_dict)

    return f'''```{{=html}}
<article class="sira-report" id="{report_id}" lang="ar" dir="rtl">
  <header class="sira-report-header" lang="en" dir="ltr">
    <span class="report-label">{label}</span>
    <a class="report-id" href="#{report_id}">{report_id}</a>
    {reference_html}
  </header>
  <div class="witness-text">
    {report["html"]}
  </div>
</article>
```'''


def render_variant_group(
    group: list[str],
    reports_by_id: dict[str, dict],
    bibliography_dict: dict[str, dict[str, str]],
) -> str:
    group_label = group[0]

    parts = [
        '::: {.callout-note collapse="true"}',
        f"## Parallel passages: `{group_label}`",
        "",
        "```{=html}",
        '<section class="sira-variant-scroll" lang="ar" dir="rtl" aria-label="Variant group">',
        '<div class="sira-variant-inner">',
    ]

    for report_id in group:
        report = reports_by_id[report_id]
        reference_html = get_report_reference_html(report_id, report["raw"], bibliography_dict)

        parts.append(
            f'''
<article class="sira-report sira-variant-card" id="{report_id}" lang="ar" dir="rtl">
  <header class="sira-report-header" lang="en" dir="ltr">
    <span class="report-label">Variant</span>
    <a class="report-id" href="#{report_id}">{report_id}</a>
    {reference_html}
  </header>
  <div class="witness-text">
    {report["html"]}
  </div>
</article>
'''
        )

    parts.extend(
        [
            "</div>",
            "</section>",
            "```",
            "",
            ":::",
            "",
        ]
    )

    return "\n".join(parts)


def append_comment_note(
    report_id: str,
    comment: str,
    footnotes: list[str],
    witness_dict: dict[str, str],
    bibliography_dict: dict[str, dict[str, str]],
    comment_counts: dict[str, int],
) -> str:
    """
    Append an editorial comment as a uniquely identified footnote and return
    the corresponding footnote reference.
    """
    comment_counts[report_id] = comment_counts.get(report_id, 0) + 1
    footnote_id = f"comment-{report_id}-{comment_counts[report_id]}"

    formatted_comment = format_comment_for_note(
        comment,
        witness_dict,
        bibliography_dict,
    )

    footnotes.append(f"[^{footnote_id}]: {formatted_comment}")

    return f"[^{footnote_id}]"


def render_report_groups(
    reports: list[dict],
    witness_dict: dict[str, str],
    bibliography_dict: dict[str, dict[str, str]],
) -> tuple[list[str], list[str]]:
    reports_by_id = {report["id"]: report for report in reports}
    variant_groups = build_variant_groups(reports)
    groups_to_render = variant_groups[:GROUP_LIMIT] if GROUP_LIMIT else variant_groups

    qmd_parts: list[str] = []
    footnotes: list[str] = []
    comment_counts: dict[str, int] = {}

    for group in groups_to_render:
        group_reports = [reports_by_id[report_id] for report_id in group]

        if len(group) == 1:
            report = group_reports[0]

            qmd_parts.append(
                render_report_article(
                    report,
                    bibliography_dict,
                    label="Passage",
                )
            )

            if report.get("comment"):
                comment_ref = append_comment_note(
                    report["id"],
                    report["comment"],
                    footnotes,
                    witness_dict,
                    bibliography_dict,
                    comment_counts,
                )
                qmd_parts.append(f"\n{comment_ref}\n")

        else:
            qmd_parts.append(
                render_variant_group(
                    group,
                    reports_by_id,
                    bibliography_dict,
                )
            )

            for report in group_reports:
                if report.get("comment"):
                    comment_ref = append_comment_note(
                        report["id"],
                        report["comment"],
                        footnotes,
                        witness_dict,
                        bibliography_dict,
                        comment_counts,
                    )
                    qmd_parts.append(
                        f"\n**Comment on passage `{report['id']}`:** {comment_ref}\n"
                    )

    return qmd_parts, footnotes


def build_witness_qmd(
    witness_path: Path,
    witness_dict: dict[str, str],
    bibliography_dict: dict[str, dict[str, str]],
) -> dict[str, object]:
    fallback_code = witness_path.stem

    source = witness_path.read_text(encoding="utf-8")
    source = clean_source_text(source, witness_path.name)

    body, arabic_title, witness_title, witness_code = strip_metadata(source, fallback_code)

    if witness_code == fallback_code and "Tag Name:" not in source:
        warnings = [f"{witness_path.name}: missing #META# Tag Name; using filename as witness code."]
    else:
        warnings = []

    output_path = OUTPUT_DIR / f"{slugify_filename(witness_code)}.qmd"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    qmd_parts = [
        "---",
        f'title: "{witness_title}"',
        'lang: "en"',
        f'witness-code: "{witness_code}"',
        'source-language: "ar"',
        "---",
        "",
        f'# <span lang="ar" dir="rtl">{html.escape(arabic_title)}</span>',
        "",
        f"**Witness code:** `{witness_code}`",
        "",
        "This witness version is generated from the encoded source file prepared for this edition.",
        "",
        "```{=html}",
        f'<div class="sira-witness" data-witness="{witness_code}">',
        "```",
        "",
    ]

    all_footnotes = []
    total_reports = 0
    total_groups = 0

    sections = split_sections(body)

    for section in sections:
        heading = render_section_heading(section)
        if heading:
            qmd_parts.extend(["", heading, ""])

        reports = parse_reports(
            section["content"],
            bibliography_dict,
            witness_code,
            warnings,
        )

        total_reports += len(reports)

        if not reports:
            continue

        variant_groups = build_variant_groups(reports)
        total_groups += len(variant_groups)

        report_qmd_parts, footnotes = render_report_groups(
            reports,
            witness_dict,
            bibliography_dict,
        )

        qmd_parts.extend(report_qmd_parts)
        all_footnotes.extend(footnotes)

    qmd_parts.extend(
        [
            "```{=html}",
            "</div>",
            "```",
            "",
        ]
    )

    if all_footnotes:
        qmd_parts.extend(
            [
                "",
                *all_footnotes,
                "",
            ]
        )

    output_path.write_text("\n".join(qmd_parts), encoding="utf-8")

    return {
        "witness_code": witness_code,
        "output_path": output_path,
        "reports": total_reports,
        "groups": total_groups,
        "footnotes": len(all_footnotes),
        "warnings": warnings,
    }


def iter_witness_files() -> list[Path]:
    if not WITNESS_DIR.exists():
        raise FileNotFoundError(f"Witness directory does not exist: {WITNESS_DIR}")

    files = [
        path
        for path in sorted(WITNESS_DIR.iterdir())
        if path.is_file()
        and not path.name.startswith(".")
        and path.suffix.lower() not in {".csv", ".tsv", ".xlsx", ".md", ".html"}
    ]

    return files

def update_quarto_yml(witness_results: list[dict[str, object]]) -> None:
    """
    Rewrite _quarto.yml so the book sidebar includes all generated witness pages.

    This keeps manually authored front matter/pages separate from generated
    witness pages, and configures Quarto/Pandoc citation processing.
    """
    witness_chapters = [
        result["output_path"].relative_to(ROOT).as_posix()
        for result in sorted(
            witness_results,
            key=lambda item: str(item["witness_code"]).lower(),
        )
    ]

    chapters = STATIC_CHAPTERS + witness_chapters + ["references.qmd"]

    lines = [
        "project:",
        "  type: book",
        "  output-dir: docs",
        "",
        "book:",
        '  title: "The Sira Project"',
        "  chapters:",
    ]

    for chapter in chapters:
        lines.append(f"    - {chapter}")

    lines.extend(
        [
            "",
            "lang: en",
            "",
            "bibliography: references.bib",
            "nocite: |",
            "  @*",
            "",
            "format:",
            "  html:",
            "    toc: true",
            "    toc-depth: 2",
            "    number-sections: false",
            "    reference-location: margin",
            "    css: assets/sira.css",
            "",
        ]
    )

    QUARTO_YML.write_text("\n".join(lines), encoding="utf-8")

    print(f"Updated {QUARTO_YML} with {len(witness_chapters)} generated witness chapter(s).")

def build_all_qmd() -> None:
    witness_records = load_witness_records()
    witness_dict = {
        code: record.get("name") or code
        for code, record in witness_records.items()
    }
    bibliography_dict = load_bibliography_dict()

    results = []

    for witness_path in iter_witness_files():
        result = build_witness_qmd(
            witness_path,
            witness_dict,
            bibliography_dict,
        )
        results.append(result)

        print(
            f"Wrote {result['output_path']} "
            f"({result['reports']} passages, {result['groups']} parallel passage groups, "
            f"{result['footnotes']} footnotes)."
        )

        for warning in result["warnings"]:
            print(f"WARNING: {warning}")


    build_witness_index_qmd(witness_records, results)
    build_references_qmd()
    build_references_bib(bibliography_dict)
    update_quarto_yml(results)

    print("")
    print(f"Built {len(results)} witness pages.")
    print(f"Loaded {len(witness_dict)} witness metadata records.")
    print(f"Loaded {len(bibliography_dict)} bibliography metadata records.")

    total_warnings = sum(len(result["warnings"]) for result in results)

    if total_warnings:
        print(f"Completed with {total_warnings} warning(s). Review them before publication.")
    else:
        print("Completed without parser warnings.")


if __name__ == "__main__":
    build_all_qmd()
    