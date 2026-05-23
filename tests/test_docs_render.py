from pathlib import Path

import pytest

from security_observatory.docs_render import render_markdown


def test_headings():
    out = render_markdown("# Top\n\n## Sub\n\n### Smaller\n")
    assert "<h1>Top</h1>" in out
    assert "<h2>Sub</h2>" in out
    assert "<h3>Smaller</h3>" in out


def test_paragraph_collapses_soft_wrap():
    out = render_markdown("First line\nstill the same paragraph.\n\nNew paragraph.\n")
    assert "<p>First line still the same paragraph.</p>" in out
    assert "<p>New paragraph.</p>" in out


def test_unordered_list():
    out = render_markdown("- one\n- two\n- three\n")
    assert out == "<ul><li>one</li><li>two</li><li>three</li></ul>"


def test_ordered_list():
    out = render_markdown("1. one\n2. two\n")
    assert out == "<ol><li>one</li><li>two</li></ol>"


def test_fenced_code_block_preserves_content_and_escapes_html():
    md = "```python\nprint('<hi>')\n```\n"
    out = render_markdown(md)
    assert '<pre><code class="language-python">' in out
    assert "print(&#x27;&lt;hi&gt;&#x27;)" in out


def test_inline_code_is_preserved_literally():
    out = render_markdown("Use `security-scan ioc .` to run.\n")
    assert "<code>security-scan ioc .</code>" in out


def test_bold_and_italic():
    out = render_markdown("This is **bold** and *italic* and _also italic_.\n")
    assert "<strong>bold</strong>" in out
    assert "<em>italic</em>" in out
    assert "<em>also italic</em>" in out


def test_links_render_with_href_and_rel():
    out = render_markdown("See [the docs](https://example.com/x) for more.\n")
    assert '<a href="https://example.com/x" rel="noreferrer">the docs</a>' in out


def test_javascript_url_is_neutralized():
    out = render_markdown("[bad](javascript:alert(1))\n")
    assert 'href="#"' in out
    assert "javascript:" not in out


def test_gfm_table_renders_thead_and_tbody():
    md = (
        "| Role | Responsibility |\n"
        "| --- | --- |\n"
        "| User | Approves proposals |\n"
        "| Agent | Reads context |\n"
    )
    out = render_markdown(md)
    assert "<table>" in out
    assert "<thead><tr><th>Role</th><th>Responsibility</th></tr></thead>" in out
    assert "<tbody><tr><td>User</td><td>Approves proposals</td></tr>" in out
    assert "<tr><td>Agent</td><td>Reads context</td></tr></tbody>" in out


def test_blockquote():
    out = render_markdown("> A note from the author.\n")
    assert "<blockquote>" in out
    assert "A note from the author." in out


def test_horizontal_rule():
    out = render_markdown("Above\n\n---\n\nBelow\n")
    assert "<hr />" in out


def test_raw_html_in_source_is_escaped():
    out = render_markdown("This <script>alert(1)</script> is not allowed.\n")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


@pytest.mark.parametrize(
    "doc_name",
    [
        "iocs.md",
        "install-hooks.md",
        "workflow-audit.md",
        "agent-lab.md",
        "tool-catalog.md",
    ],
)
def test_renders_every_catalog_doc_without_raw_markers(doc_name):
    repo_root = Path(__file__).resolve().parents[1]
    source = (repo_root / "docs" / doc_name).read_text(encoding="utf-8")
    out = render_markdown(source)

    # The H1 from the source must become an actual <h1> tag.
    first_line = source.splitlines()[0]
    assert first_line.startswith("# "), "fixture should start with an H1"
    assert f"<h1>{first_line[2:]}</h1>" in out

    # No raw markdown headings should leak through unconverted.
    for raw in ("\n# ", "\n## ", "\n### "):
        assert raw not in out, f"raw markdown heading leaked through in {doc_name}"
