"""Minimal CommonMark/GFM subset renderer for in-app documentation.

The dashboard ships first-party docs (IOC packs, install hook classifier, etc.)
and DëvSec's whole stance is local-first — so docs render inside the product
rather than bouncing the user to GitHub. The project keeps zero runtime
dependencies; rather than pulling in a markdown library, this module renders
the subset of Markdown that the in-repo ``docs/*.md`` files actually use:

- ATX headings (``#`` through ``######``)
- Paragraphs
- Fenced code blocks with optional language
- Inline code, bold (``**x**``), italic (``*x*`` / ``_x_``), links
- Unordered (``-`` / ``*``) and ordered (``1.``) lists, including nesting
- GFM tables (``| col | col |`` with ``|---|`` separator)
- Blockquotes (``>``)
- Horizontal rules (``---``)

The renderer is deliberately small: it escapes every text fragment before
inserting it into the output, so a malicious ``docs/`` file cannot inject HTML
into the dashboard chrome. Anything it doesn't understand renders as escaped
text inside a paragraph — readers see the source character verbatim rather
than something silently dropped.
"""

from __future__ import annotations

import html
import re


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_HR_RE = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})\s*$")
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})\s*([^\s`~]*)\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")
_UL_RE = re.compile(r"^(\s*)([-*+])\s+(.*)$")
_OL_RE = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")
_BLOCKQUOTE_RE = re.compile(r"^>\s?(.*)$")

# Inline patterns: order matters — code first so its contents are not re-parsed.
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_BOLD_RE = re.compile(r"\*\*([^\*]+)\*\*")
_ITALIC_STAR_RE = re.compile(r"(?<!\*)\*([^\*\n]+)\*(?!\*)")
_ITALIC_UNDER_RE = re.compile(r"(?<!\w)_([^_\n]+)_(?!\w)")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_AUTOLINK_RE = re.compile(r"<(https?://[^>\s]+)>")


def render_markdown(text: str) -> str:
    """Render ``text`` (Markdown) as a safe HTML fragment."""

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        fence = _FENCE_RE.match(line.rstrip())
        if fence:
            i, block = _consume_fence(lines, i, fence.group(1), fence.group(2))
            out.append(block)
            continue

        if _HR_RE.match(line.rstrip()):
            out.append("<hr />")
            i += 1
            continue

        heading = _HEADING_RE.match(line.rstrip())
        if heading:
            level = len(heading.group(1))
            out.append(f"<h{level}>{_render_inline(heading.group(2))}</h{level}>")
            i += 1
            continue

        if i + 1 < n and "|" in line and _TABLE_SEP_RE.match(lines[i + 1]):
            i, block = _consume_table(lines, i)
            out.append(block)
            continue

        if _BLOCKQUOTE_RE.match(line):
            i, block = _consume_blockquote(lines, i)
            out.append(block)
            continue

        if _UL_RE.match(line) or _OL_RE.match(line):
            i, block = _consume_list(lines, i)
            out.append(block)
            continue

        i, block = _consume_paragraph(lines, i)
        out.append(block)

    return "\n".join(out)


def _consume_fence(lines: list[str], start: int, fence: str, language: str) -> tuple[int, str]:
    body: list[str] = []
    i = start + 1
    n = len(lines)
    while i < n:
        candidate = lines[i].rstrip()
        if candidate.startswith(fence) and candidate.strip(fence[0]) == "":
            i += 1
            break
        body.append(lines[i])
        i += 1
    lang_class = f' class="language-{html.escape(language)}"' if language else ""
    escaped = html.escape("\n".join(body))
    return i, f"<pre><code{lang_class}>{escaped}</code></pre>"


def _consume_paragraph(lines: list[str], start: int) -> tuple[int, str]:
    buf: list[str] = []
    i = start
    n = len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            break
        if _HEADING_RE.match(line.rstrip()):
            break
        if _HR_RE.match(line.rstrip()):
            break
        if _FENCE_RE.match(line.rstrip()):
            break
        if _UL_RE.match(line) or _OL_RE.match(line):
            break
        if _BLOCKQUOTE_RE.match(line):
            break
        if i + 1 < n and "|" in line and _TABLE_SEP_RE.match(lines[i + 1]):
            break
        buf.append(line.strip())
        i += 1
    inline = " ".join(buf)
    return i, f"<p>{_render_inline(inline)}</p>"


def _consume_blockquote(lines: list[str], start: int) -> tuple[int, str]:
    body: list[str] = []
    i = start
    n = len(lines)
    while i < n:
        match = _BLOCKQUOTE_RE.match(lines[i])
        if not match:
            break
        body.append(match.group(1))
        i += 1
    inner = render_markdown("\n".join(body))
    return i, f"<blockquote>{inner}</blockquote>"


def _consume_list(lines: list[str], start: int) -> tuple[int, str]:
    ul_first = _UL_RE.match(lines[start])
    ol_first = _OL_RE.match(lines[start])
    assert ul_first or ol_first
    ordered = ol_first is not None
    base_indent = len((ul_first or ol_first).group(1))

    items: list[list[str]] = []
    i = start
    n = len(lines)
    current_item: list[str] | None = None
    while i < n:
        line = lines[i]
        if not line.strip():
            # blank inside a list — continuation only if next line is indented
            if i + 1 < n and lines[i + 1].startswith(" " * (base_indent + 2)):
                if current_item is not None:
                    current_item.append("")
                i += 1
                continue
            break

        ul = _UL_RE.match(line)
        ol = _OL_RE.match(line)
        marker_match = ol if ordered else ul
        other_marker_match = ul if ordered else ol
        indent = len(marker_match.group(1)) if marker_match else (
            len(other_marker_match.group(1)) if other_marker_match else None
        )

        if marker_match and indent == base_indent:
            current_item = [marker_match.group(3)]
            items.append(current_item)
            i += 1
            continue
        if other_marker_match and indent == base_indent:
            # A different list type at this indent — end this list.
            break
        if current_item is not None and (line.startswith(" " * (base_indent + 2)) or (marker_match and indent is not None and indent > base_indent)):
            current_item.append(line[base_indent + 2:] if line.startswith(" " * (base_indent + 2)) else line.lstrip())
            i += 1
            continue
        break

    tag = "ol" if ordered else "ul"
    rendered_items: list[str] = []
    for item in items:
        if len(item) == 1:
            rendered_items.append(f"<li>{_render_inline(item[0])}</li>")
            continue
        # Multi-line: first line is the leading paragraph, the rest may be
        # nested lists, code, or continuation text. Render through the block
        # parser so nested structures (sub-lists, code) render correctly.
        head = _render_inline(item[0])
        tail_text = "\n".join(item[1:]).rstrip()
        if not tail_text:
            rendered_items.append(f"<li>{head}</li>")
            continue
        rendered_tail = render_markdown(tail_text)
        rendered_items.append(f"<li>{head}\n{rendered_tail}</li>")
    return i, f"<{tag}>" + "".join(rendered_items) + f"</{tag}>"


def _consume_table(lines: list[str], start: int) -> tuple[int, str]:
    header_cells = _split_table_row(lines[start])
    alignments = _table_alignments(lines[start + 1])
    rows: list[list[str]] = []
    i = start + 2
    n = len(lines)
    while i < n:
        line = lines[i]
        if not line.strip() or "|" not in line:
            break
        rows.append(_split_table_row(line))
        i += 1

    def th(cell: str, align: str | None) -> str:
        attr = f' style="text-align:{align}"' if align else ""
        return f"<th{attr}>{_render_inline(cell)}</th>"

    def td(cell: str, align: str | None) -> str:
        attr = f' style="text-align:{align}"' if align else ""
        return f"<td{attr}>{_render_inline(cell)}</td>"

    head = "<thead><tr>" + "".join(th(cell, alignments[idx] if idx < len(alignments) else None) for idx, cell in enumerate(header_cells)) + "</tr></thead>"
    body_rows = []
    for row in rows:
        body_rows.append(
            "<tr>" + "".join(td(cell, alignments[idx] if idx < len(alignments) else None) for idx, cell in enumerate(row)) + "</tr>"
        )
    body = "<tbody>" + "".join(body_rows) + "</tbody>" if body_rows else ""
    return i, f"<table>{head}{body}</table>"


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _table_alignments(sep_line: str) -> list[str | None]:
    cells = _split_table_row(sep_line)
    out: list[str | None] = []
    for cell in cells:
        cell = cell.strip()
        if cell.startswith(":") and cell.endswith(":"):
            out.append("center")
        elif cell.endswith(":"):
            out.append("right")
        elif cell.startswith(":"):
            out.append("left")
        else:
            out.append(None)
    return out


def _render_inline(text: str) -> str:
    """Apply inline markdown to escaped text, preserving raw code literally."""

    placeholders: list[str] = []

    def stash_code(match: re.Match[str]) -> str:
        placeholders.append(f"<code>{html.escape(match.group(1))}</code>")
        return f"\x00{len(placeholders) - 1}\x00"

    working = _INLINE_CODE_RE.sub(stash_code, text)
    working = html.escape(working)

    def link_sub(match: re.Match[str]) -> str:
        label = match.group(1)
        href = match.group(2)
        safe_href = _safe_url(href)
        return f'<a href="{safe_href}" rel="noreferrer">{label}</a>'

    # Replace links and inline emphasis on the escaped string.
    working = _LINK_RE.sub(link_sub, working)
    working = _AUTOLINK_RE.sub(lambda m: f'<a href="{_safe_url(m.group(1))}" rel="noreferrer">{m.group(1)}</a>', working)
    working = _BOLD_RE.sub(r"<strong>\1</strong>", working)
    working = _ITALIC_STAR_RE.sub(r"<em>\1</em>", working)
    working = _ITALIC_UNDER_RE.sub(r"<em>\1</em>", working)

    def restore(match: re.Match[str]) -> str:
        index = int(match.group(1))
        return placeholders[index]

    working = re.sub(r"\x00(\d+)\x00", restore, working)
    return working


def _safe_url(href: str) -> str:
    candidate = href.strip()
    lowered = candidate.lower()
    if lowered.startswith(("http://", "https://", "mailto:", "/")):
        return html.escape(candidate, quote=True)
    if lowered.startswith("#"):
        return html.escape(candidate, quote=True)
    # Reject javascript:, data:, vbscript:, etc. — render as inert text fragment.
    if ":" in candidate.split("/")[0]:
        return "#"
    return html.escape(candidate, quote=True)
