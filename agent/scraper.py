"""
Project HER – Article Scraper
Extracts article content from URLs or processes raw text input.
"""

from __future__ import annotations

import json
import re
import logging
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class ArticleData:
    """Structured representation of a scraped article."""

    title: str = ""
    text: str = ""
    authors: list[str] = field(default_factory=list)
    publish_date: Optional[str] = None
    source_url: Optional[str] = None
    top_image: Optional[str] = None
    summary: str = ""
    word_count: int = 0

    def __post_init__(self):
        self.word_count = len(self.text.split()) if self.text else 0


class ArticleScraper:
    """Scrapes and parses articles from URLs or raw text."""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def scrape(self, input_source: str) -> ArticleData:
        """
        Main entry point – accepts a URL or raw text.

        Args:
            input_source: URL string or raw article text.

        Returns:
            ArticleData with extracted content.
        """
        if self._is_url(input_source):
            logger.info("Detected URL input – scraping: %s", input_source)
            return self._scrape_url(input_source)
        else:
            logger.info("Detected raw text input (%d chars)", len(input_source))
            return self._process_raw_text(input_source)

    def scrape_multiple(self, sources: list[str]) -> ArticleData:
        """
        Scrape multiple URLs/texts and combine into a single ArticleData.
        Used by Deep Dive mode for multi-source synthesis.

        Args:
            sources: List of URL strings or raw text inputs.

        Returns:
            Combined ArticleData with all sources merged.
        """
        if not sources:
            raise ValueError("No sources provided for multi-source scraping.")

        all_articles: list[ArticleData] = []
        for i, source in enumerate(sources):
            source = source.strip()
            if not source:
                continue
            try:
                article = self.scrape(source)
                if article.text and article.word_count >= 20:
                    all_articles.append(article)
                    logger.info(
                        "Source %d/%d scraped: '%s' (%d words)",
                        i + 1, len(sources), article.title[:50], article.word_count,
                    )
                else:
                    logger.warning("Source %d/%d too short, skipping", i + 1, len(sources))
            except Exception as e:
                logger.warning("Source %d/%d failed: %s — skipping", i + 1, len(sources), e)

        if not all_articles:
            raise ValueError("No valid content extracted from any source.")

        # Combine into a single ArticleData
        if len(all_articles) == 1:
            return all_articles[0]

        # Multi-source merge
        combined_title = " | ".join(a.title for a in all_articles if a.title)[:200]
        combined_text_parts = []
        for i, article in enumerate(all_articles, 1):
            source_label = article.source_url or f"Source {i}"
            combined_text_parts.append(
                f"=== SOURCE {i}: {article.title} ===\n"
                f"(from: {source_label})\n\n"
                f"{article.text}\n"
            )
        combined_text = "\n\n".join(combined_text_parts)

        combined = ArticleData(
            title=combined_title,
            text=combined_text,
            authors=[a for art in all_articles for a in art.authors],
            source_url=all_articles[0].source_url,
            top_image=next((a.top_image for a in all_articles if a.top_image), None),
            summary=" | ".join(a.summary for a in all_articles if a.summary),
        )
        logger.info(
            "Multi-source merge: %d sources → %d words total",
            len(all_articles), combined.word_count,
        )
        return combined

    # ── URL Scraping ──────────────────────────────────────

    def _scrape_url(self, url: str) -> ArticleData:
        """Scrape article from a URL using newspaper3k with BS4 fallback."""
        # Try newspaper3k first
        try:
            return self._scrape_with_newspaper(url)
        except Exception as e:
            logger.warning("newspaper3k failed: %s – falling back to BS4", e)

        # Fallback to BeautifulSoup (includes JSON-LD extraction)
        return self._scrape_with_bs4(url)

    def _scrape_with_newspaper(self, url: str) -> ArticleData:
        """Use newspaper3k for structured article extraction."""
        from newspaper import Article

        article = Article(url)
        article.download()
        article.parse()

        if not article.text or len(article.text.split()) < 50:
            raise ValueError("newspaper3k extracted insufficient text")

        # nlp() may fail if NLTK data is missing – non-critical
        try:
            article.nlp()  # generates summary, keywords
        except Exception as e:
            logger.warning("newspaper3k nlp() failed (non-critical): %s", e)

        return ArticleData(
            title=article.title or "Untitled",
            text=self._clean_text(article.text),
            authors=list(article.authors) if article.authors else [],
            publish_date=str(article.publish_date) if article.publish_date else None,
            source_url=url,
            top_image=article.top_image,
            summary=getattr(article, "summary", "") or "",
        )

    def _scrape_with_bs4(self, url: str) -> ArticleData:
        """Fallback scraper using BeautifulSoup + JSON-LD."""
        response = self.session.get(url, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # Extract title
        title = ""
        if soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)
        elif soup.title:
            title = soup.title.get_text(strip=True)

        # Extract top image
        top_image = None
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            top_image = og_image["content"]

        # --- Strategy 1: JSON-LD articleBody (most reliable) ---
        text = self._extract_json_ld_body(soup)
        if text and len(text.split()) >= 50:
            logger.info("Extracted article via JSON-LD (%d words)", len(text.split()))
            return ArticleData(
                title=title or "Untitled",
                text=self._clean_text(text),
                source_url=url,
                top_image=top_image,
            )

        # --- Strategy 2: Standard <p>-based article containers ---
        # Remove unwanted elements first
        for tag in soup.find_all(
            ["script", "style", "nav", "footer", "header", "aside", "form"]
        ):
            tag.decompose()

        text = self._extract_main_content(soup)
        if text and len(text.split()) >= 50:
            logger.info("Extracted article via <p> containers (%d words)", len(text.split()))
            return ArticleData(
                title=title or "Untitled",
                text=self._clean_text(text),
                source_url=url,
                top_image=top_image,
            )

        # --- Strategy 3: Direct text in known article divs ---
        text = self._extract_direct_text(soup)
        if text and len(text.split()) >= 50:
            logger.info("Extracted article via direct text (%d words)", len(text.split()))
            return ArticleData(
                title=title or "Untitled",
                text=self._clean_text(text),
                source_url=url,
                top_image=top_image,
            )

        # --- Strategy 4: Last resort – all <p> tags ---
        paragraphs = soup.find_all("p")
        text = " ".join(p.get_text(strip=True) for p in paragraphs)
        logger.warning("Using all-<p> fallback (%d words)", len(text.split()))

        return ArticleData(
            title=title or "Untitled",
            text=self._clean_text(text),
            source_url=url,
            top_image=top_image,
        )

    def _extract_json_ld_body(self, soup: BeautifulSoup) -> str:
        """Extract articleBody from JSON-LD structured data."""
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                # Handle single object
                if isinstance(data, dict):
                    if "articleBody" in data:
                        return data["articleBody"]
                # Handle array of objects
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "articleBody" in item:
                            return item["articleBody"]
            except (json.JSONDecodeError, TypeError):
                continue
        return ""

    def _extract_direct_text(self, soup: BeautifulSoup) -> str:
        """Extract text directly from known article containers (not just <p>)."""
        # Some sites (e.g., Times of India) store text directly in divs
        direct_text_selectors = [
            "div._s30J",                # Times of India
            "div[data-articlebody]",    # Generic data attribute
            ".artData",                 # India Today variants
            "div.article__content",     # Various news sites
            "div.story_details",        # Economic Times
            "div.content_text",         # NDTV variants
            ".article-txt",            # Hindustan Times
        ]
        for selector in direct_text_selectors:
            container = soup.select_one(selector)
            if container:
                text = container.get_text(separator=" ", strip=True)
                if len(text) > 200:
                    return text
        return ""

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extract the main article text from HTML."""
        # Look for common article containers
        content_selectors = [
            "article",
            '[role="main"]',
            ".article-body",
            ".post-content",
            ".entry-content",
            ".article-content",
            ".story-body",
            "#article-body",
            "main",
        ]

        for selector in content_selectors:
            container = soup.select_one(selector)
            if container:
                paragraphs = container.find_all("p")
                if paragraphs:
                    text = " ".join(p.get_text(strip=True) for p in paragraphs)
                    if len(text) > 200:
                        return text

        # Fallback: collect all <p> tags
        paragraphs = soup.find_all("p")
        text = " ".join(p.get_text(strip=True) for p in paragraphs)
        return text

    # ── Raw Text Processing ──────────────────────────────

    def _process_raw_text(self, text: str) -> ArticleData:
        """Process raw pasted article text."""
        clean = self._clean_text(text)
        lines = clean.split("\n")

        # Use first non-empty line as title
        title = "Untitled"
        body_start = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and len(stripped) > 5:
                title = stripped[:120]
                body_start = i + 1
                break

        body = "\n".join(lines[body_start:]).strip()
        if not body:
            body = clean  # fallback: use all text

        return ArticleData(
            title=title,
            text=body,
        )

    # ── Utilities ─────────────────────────────────────────

    @staticmethod
    def _is_url(text: str) -> bool:
        """Check whether the input looks like a URL."""
        text = text.strip()
        return bool(
            re.match(r"^https?://", text, re.IGNORECASE)
            or text.startswith("www.")
        )

    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean extracted text: normalize whitespace, remove artifacts."""
        # Remove multiple newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Remove multiple spaces
        text = re.sub(r" {2,}", " ", text)
        # Remove common artifacts
        text = re.sub(r"Advertisement\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"Share this article.*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"Read more:.*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"Subscribe to.*", "", text, flags=re.IGNORECASE)
        return text.strip()
