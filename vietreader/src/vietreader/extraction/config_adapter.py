"""Site adapter driven by config/sites/*.yml (selectolax-based). See config/sites/_example.yml."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

import yaml
from selectolax.parser import HTMLParser, Node

from vietreader.core.models import Chapter
from vietreader.core.normalize import normalize_text, split_paragraphs
from vietreader.extraction.base import ExtractionError

_URL_ATTRS = {"href", "src"}


@dataclass(frozen=True, slots=True)
class SiteConfig:
    domain: str
    title: str
    content: str
    paragraph_split: str = "newline"
    next_link: str | None = None
    prev_link: str | None = None
    strip_selectors: tuple[str, ...] = ()

    @classmethod
    def from_yaml(cls, raw: str) -> SiteConfig:
        data = yaml.safe_load(raw)
        return cls(
            domain=data["domain"],
            title=data["title"],
            content=data["content"],
            paragraph_split=data.get("paragraph_split", "newline"),
            next_link=data.get("next_link"),
            prev_link=data.get("prev_link"),
            strip_selectors=tuple(data.get("strip_selectors") or ()),
        )


def _split_selector_attr(selector: str) -> tuple[str, str | None]:
    """"a#next@href" -> ("a#next", "href"); "h1.title" -> ("h1.title", None)."""
    css, sep, attr = selector.rpartition("@")
    return (css, attr) if sep else (selector, None)


def _extract_field(tree: HTMLParser, selector: str | None, base_url: str) -> str | None:
    if not selector:
        return None
    css, attr = _split_selector_attr(selector)
    node = tree.css_first(css)
    if node is None:
        return None
    if attr is None:
        text = node.text(strip=True)
        return text or None
    value = node.attributes.get(attr)
    if value is None:
        return None
    return urljoin(base_url, value) if attr in _URL_ATTRS else value


def _extract_paragraphs(content_node: Node, paragraph_split: str) -> list[str]:
    if paragraph_split == "newline":
        raw_text = content_node.text(deep=True, separator="\n", strip=True)
        return split_paragraphs(normalize_text(raw_text))
    paragraphs = []
    for node in content_node.css(paragraph_split):
        text = node.text(deep=True, separator=" ", strip=True)
        if text:
            paragraphs.append(normalize_text(text))
    return paragraphs


class ConfigAdapter:
    def __init__(self, config: SiteConfig) -> None:
        self.config = config

    def extract(self, html: str, source_url: str) -> Chapter:
        if not html or not html.strip():
            raise ExtractionError(f"empty HTML input for {source_url!r}")

        tree = HTMLParser(html)

        title = _extract_field(tree, self.config.title, source_url) or ""
        next_url = _extract_field(tree, self.config.next_link, source_url)
        prev_url = _extract_field(tree, self.config.prev_link, source_url)

        content_css, _ = _split_selector_attr(self.config.content)
        content_node = tree.css_first(content_css)
        if content_node is None:
            raise ExtractionError(
                f"content selector {self.config.content!r} matched nothing for {source_url!r}"
            )

        for strip_selector in self.config.strip_selectors:
            for node in content_node.css(strip_selector):
                node.decompose()

        paragraphs = _extract_paragraphs(content_node, self.config.paragraph_split)

        return Chapter(
            title=normalize_text(title),
            paragraphs=paragraphs,
            next_url=next_url,
            prev_url=prev_url,
            source_url=source_url,
        )
