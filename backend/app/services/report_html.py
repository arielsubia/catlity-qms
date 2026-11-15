"""Reduce a report section to the marks the editor prints.

The draft is stored as text and later printed in the browser. Bold, italic,
lists, and paragraphs stay. Every other tag is removed, including script, so
a saved section cannot run when the page prints it.
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

_ALLOWED = {"p", "br", "strong", "em", "b", "i", "ul", "ol", "li"}
_DROPPED = {"script", "style"}
_TAGS = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


class _Cleaner(HTMLParser):
    """Copy allowed tags and escape their text. Attributes are left behind."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._drop_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        name = tag.lower()
        if name in _DROPPED:
            self._drop_depth += 1
            return
        if self._drop_depth:
            return
        if name == "div":
            self._parts.append("<p>")
            return
        if name == "br":
            self._parts.append("<br>")
            return
        if name in _ALLOWED:
            self._parts.append(f"<{name}>")

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if name in _DROPPED:
            if self._drop_depth:
                self._drop_depth -= 1
            return
        if self._drop_depth:
            return
        if name == "div":
            self._parts.append("</p>")
            return
        if name == "br":
            return
        if name in _ALLOWED:
            self._parts.append(f"</{name}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() != "br":
            self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self._drop_depth or not data:
            return
        self._parts.append(html.escape(data))

    def result(self) -> str:
        return "".join(self._parts)


def sanitize_report_html(value: str) -> str:
    """Return the section with only the tags the print view understands."""
    cleaner = _Cleaner()
    cleaner.feed(value)
    cleaner.close()
    return cleaner.result()


def report_plain_text(value: str) -> str:
    """Visible words of a section, used to reject an empty draft."""
    text = _TAGS.sub(" ", sanitize_report_html(value))
    text = html.unescape(text).replace("\xa0", " ")
    return _SPACE.sub(" ", text).strip()
