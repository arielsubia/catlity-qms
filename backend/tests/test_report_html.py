"""Section HTML keeps the marks the browser print view can show."""

from app.services.report_html import report_plain_text, sanitize_report_html


def test_plain_text_and_bold_are_kept() -> None:
    assert sanitize_report_html("A & B") == "A &amp; B"
    assert sanitize_report_html('<b onclick="x">Listo</b>') == "<b>Listo</b>"
    assert report_plain_text("<b>Listo</b>") == "Listo"


def test_script_is_removed_and_a_div_becomes_a_paragraph() -> None:
    cleaned = sanitize_report_html("<script>alert(1)</script><div>Listo</div>")

    assert cleaned == "<p>Listo</p>"
    assert "script" not in cleaned
    assert report_plain_text("<script>alert(1)</script>") == ""
    assert report_plain_text("   ") == ""
