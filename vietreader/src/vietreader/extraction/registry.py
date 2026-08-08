"""Chooses a site adapter by domain (config/sites/<domain>.yml), falls back to generic."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from vietreader.core.models import Chapter
from vietreader.extraction.base import Extractor
from vietreader.extraction.config_adapter import ConfigAdapter, SiteConfig
from vietreader.extraction.generic import GenericExtractor

DEFAULT_SITES_DIR = Path(__file__).resolve().parents[3] / "config" / "sites"


class Registry:
    def __init__(self, sites_dir: Path | None = None) -> None:
        self._sites_dir = sites_dir or DEFAULT_SITES_DIR
        self._generic = GenericExtractor()

    def _load_config(self, domain: str) -> SiteConfig | None:
        candidate = self._sites_dir / f"{domain}.yml"
        if not candidate.is_file():
            return None
        return SiteConfig.from_yaml(candidate.read_text(encoding="utf-8"))

    def get_extractor(self, url: str) -> Extractor:
        domain = urlparse(url).hostname or ""
        config = self._load_config(domain)
        if config is not None:
            return ConfigAdapter(config)
        return self._generic

    def extract(self, html: str, source_url: str) -> Chapter:
        return self.get_extractor(source_url).extract(html, source_url)
