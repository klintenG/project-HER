"""
Project HER v2.0 – Visual Asset Finder
Searches for relevant images/videos from Pexels with retry logic,
async parallel downloads, and intelligent fallback strategies.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import requests
import aiohttp

import config
from agent.analyzer import KeyPoint
from utils.helpers import slugify, ensure_dir

logger = logging.getLogger(__name__)


@dataclass
class ImageAsset:
    """A downloaded image or video asset for a scene."""
    key_point_index: int
    local_path: Path
    source_url: str
    photographer: str = ""
    alt_text: str = ""
    asset_type: str = "image"  # "image" or "video"


class VisualFinder:
    """
    Finds and downloads relevant royalty-free visuals from Pexels.
    
    v2.0 enhancements:
    - Concurrent async downloads (3-6x faster)
    - Retry logic with exponential backoff
    - Pexels Video API support for B-roll
    - Intelligent fallback: visual_query → headline → broader terms → placeholder
    - Image quality scoring
    """

    PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"
    PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.PEXELS_API_KEY
        if not self.api_key:
            raise ValueError(
                "Pexels API key is required. Set PEXELS_API_KEY in .env file."
            )
        self.session = requests.Session()
        self.session.headers.update({"Authorization": self.api_key})

    def find_images(
        self,
        key_points: list[KeyPoint],
        output_dir: Path,
        video_format: str = "vertical",
        theme: str = "",
    ) -> list[ImageAsset]:
        """
        Find and download images for each key point using async parallel downloads.
        Falls back to sync if async fails.
        
        If theme is "explainer", visual queries are modified to prefer
        illustration-style, flat, minimal imagery.
        """
        # Modify visual queries for explainer mode
        if theme == "explainer":
            for kp in key_points:
                kp.visual_query = f"{kp.visual_query} minimal flat illustration"

        try:
            return asyncio.run(
                self._find_images_async(key_points, output_dir, video_format)
            )
        except Exception as e:
            logger.warning("Async download failed, falling back to sync: %s", e)
            return self._find_images_sync(key_points, output_dir, video_format)

    async def _find_images_async(
        self,
        key_points: list[KeyPoint],
        output_dir: Path,
        video_format: str,
    ) -> list[ImageAsset]:
        """Download images concurrently using aiohttp."""
        images_dir = ensure_dir(output_dir / "images")
        orientation = self._format_to_orientation(video_format)

        async with aiohttp.ClientSession(
            headers={"Authorization": self.api_key},
            timeout=aiohttp.ClientTimeout(total=config.API_TIMEOUT)
        ) as session:
            tasks = [
                self._async_search_and_download(
                    session, kp, images_dir, orientation
                )
                for kp in key_points
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        assets = []
        for i, result in enumerate(results):
            if isinstance(result, ImageAsset):
                assets.append(result)
            else:
                if isinstance(result, Exception):
                    logger.warning(
                        "Async download failed for point %d: %s", i, result
                    )
                placeholder = self._create_placeholder(key_points[i], images_dir)
                assets.append(placeholder)

        logger.info(
            "Downloaded %d images for %d key points (async)",
            len(assets), len(key_points),
        )
        return assets

    def _find_images_sync(
        self,
        key_points: list[KeyPoint],
        output_dir: Path,
        video_format: str,
    ) -> list[ImageAsset]:
        """Synchronous fallback for image downloading."""
        images_dir = ensure_dir(output_dir / "images")
        orientation = self._format_to_orientation(video_format)

        assets = []
        for kp in key_points:
            logger.info(
                "Searching images for key point %d: '%s'",
                kp.index, kp.visual_query,
            )
            asset = self._search_and_download_with_retry(kp, images_dir, orientation)
            if asset:
                assets.append(asset)
            else:
                placeholder = self._create_placeholder(kp, images_dir)
                assets.append(placeholder)

        logger.info("Downloaded %d images for %d key points", len(assets), len(key_points))
        return assets

    def _search_and_download_with_retry(
        self,
        key_point: KeyPoint,
        output_dir: Path,
        orientation: str,
    ) -> Optional[ImageAsset]:
        """Search and download with retry logic and multiple fallback queries."""
        # Try B-roll video first
        broll = self._search_video_broll(key_point, output_dir, orientation)
        if broll:
            return broll

        queries = [
            key_point.visual_query,
            key_point.headline,
            # Broader fallback: extract key nouns
            " ".join(key_point.visual_query.split()[:3]),
        ]

        for query in queries:
            for attempt in range(config.MAX_RETRIES):
                asset = self._search_and_download(
                    key_point, output_dir, orientation, query_override=query
                )
                if asset:
                    return asset

                if attempt < config.MAX_RETRIES - 1:
                    wait = config.RETRY_BACKOFF ** attempt * 0.5
                    logger.info("Retry %d for '%s' in %.1fs...", attempt + 1, query, wait)
                    time.sleep(wait)

            logger.warning("All retries exhausted for query: '%s'", query)

        return None

    def _search_and_download(
        self,
        key_point: KeyPoint,
        output_dir: Path,
        orientation: str,
        query_override: Optional[str] = None,
    ) -> Optional[ImageAsset]:
        """Search Pexels and download the best matching image."""
        query = query_override or key_point.visual_query

        try:
            response = self.session.get(
                self.PEXELS_SEARCH_URL,
                params={
                    "query": query,
                    "per_page": config.IMAGE_SEARCH_COUNT,
                    "orientation": orientation,
                    "size": "large",
                },
                timeout=config.API_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

            photos = data.get("photos", [])
            if not photos:
                return None

            # Pick best image (prefer higher resolution)
            photo = self._select_best_photo(photos, orientation)

            # Choose resolution
            if orientation == "portrait":
                img_url = photo["src"].get("portrait") or photo["src"]["large2x"]
            elif orientation == "landscape":
                img_url = photo["src"].get("landscape") or photo["src"]["large2x"]
            else:
                img_url = photo["src"]["large2x"]

            # Download
            filename = f"scene_{key_point.index}_{slugify(query[:30])}.jpg"
            local_path = output_dir / filename

            img_response = self.session.get(img_url, timeout=30)
            img_response.raise_for_status()
            local_path.write_bytes(img_response.content)

            logger.info(
                "Downloaded image: %s (%d KB)", filename,
                len(img_response.content) // 1024,
            )

            return ImageAsset(
                key_point_index=key_point.index,
                local_path=local_path,
                source_url=photo["url"],
                photographer=photo.get("photographer", "Unknown"),
                alt_text=photo.get("alt", query),
                asset_type="image",
            )

        except requests.RequestException as e:
            logger.error("Pexels API error for query '%s': %s", query, e)
            return None

    def _select_best_photo(self, photos: list[dict], orientation: str) -> dict:
        """Select the best photo from candidates based on resolution and relevance."""
        if len(photos) == 1:
            return photos[0]

        # Score by resolution (higher is better)
        scored = []
        for photo in photos:
            width = photo.get("width", 0)
            height = photo.get("height", 0)
            score = width * height

            # Prefer correct aspect ratio
            if orientation == "portrait" and height > width:
                score *= 1.5
            elif orientation == "landscape" and width > height:
                score *= 1.5

            scored.append((score, photo))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    async def _async_search_and_download(
        self,
        session: aiohttp.ClientSession,
        key_point: KeyPoint,
        output_dir: Path,
        orientation: str,
    ) -> ImageAsset:
        """Async search and download a single image (tries B-roll video first)."""
        # Try B-roll video first
        broll = await self._async_search_video_broll(
            session, key_point, output_dir, orientation
        )
        if broll:
            return broll

        queries = [key_point.visual_query, key_point.headline]

        for query in queries:
            params = {
                "query": query,
                "per_page": config.IMAGE_SEARCH_COUNT,
                "orientation": orientation,
                "size": "large",
            }

            try:
                async with session.get(
                    self.PEXELS_SEARCH_URL, params=params
                ) as resp:
                    data = await resp.json()

                photos = data.get("photos", [])
                if not photos:
                    continue

                photo = self._select_best_photo(photos, orientation)

                if orientation == "portrait":
                    img_url = photo["src"].get("portrait") or photo["src"]["large2x"]
                elif orientation == "landscape":
                    img_url = photo["src"].get("landscape") or photo["src"]["large2x"]
                else:
                    img_url = photo["src"]["large2x"]

                filename = f"scene_{key_point.index}_{slugify(query[:30])}.jpg"
                local_path = output_dir / filename

                async with session.get(img_url) as img_resp:
                    content = await img_resp.read()
                    local_path.write_bytes(content)

                logger.info(
                    "Downloaded image: %s (%d KB) [async]",
                    filename, len(content) // 1024,
                )

                return ImageAsset(
                    key_point_index=key_point.index,
                    local_path=local_path,
                    source_url=photo["url"],
                    photographer=photo.get("photographer", "Unknown"),
                    alt_text=photo.get("alt", query),
                    asset_type="image",
                )
            except Exception as e:
                logger.warning("Async search failed for '%s': %s", query, e)
                continue

        raise ValueError(f"No photos found for key point {key_point.index}")

    def _create_placeholder(self, key_point: KeyPoint, output_dir: Path) -> ImageAsset:
        """Create a styled placeholder image when no image is found."""
        from PIL import Image, ImageDraw, ImageFont

        fmt = config.VIDEO_FORMATS.get(
            config.DEFAULT_VIDEO_FORMAT, config.VIDEO_FORMATS["vertical"]
        )
        width, height = fmt["width"], fmt["height"]

        # Create gradient background
        img = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(img)

        # Gradient from dark blue to dark purple
        for y in range(height):
            ratio = y / height
            r = int(20 + 30 * ratio)
            g = int(15 + 10 * ratio)
            b = int(40 + 30 * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # Add text
        text = key_point.headline
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
        except (OSError, IOError):
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 48)
            except (OSError, IOError):
                font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        draw.text((x, y), text, fill="white", font=font)

        filename = f"scene_{key_point.index}_placeholder.jpg"
        local_path = output_dir / filename
        img.save(local_path, "JPEG", quality=90)

        return ImageAsset(
            key_point_index=key_point.index,
            local_path=local_path,
            source_url="placeholder",
            photographer="Generated",
            alt_text=text,
        )

    # ══════════════════════════════════════════════════════
    # PEXELS VIDEO B-ROLL
    # ══════════════════════════════════════════════════════

    def _search_video_broll(
        self,
        key_point: KeyPoint,
        output_dir: Path,
        orientation: str,
    ) -> Optional[ImageAsset]:
        """Search Pexels Videos API and download a short B-roll clip."""
        if not config.USE_VIDEO_BROLL:
            return None

        query = key_point.visual_query
        try:
            response = self.session.get(
                self.PEXELS_VIDEO_URL,
                params={
                    "query": query,
                    "per_page": 5,
                    "orientation": orientation,
                    "size": "medium",
                },
                timeout=config.API_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

            videos = data.get("videos", [])
            if not videos:
                return None

            # Pick the best video (shortest suitable clip, prefer HD)
            video = self._select_best_video(videos, orientation)
            if not video:
                return None

            # Find the best video file (prefer HD, mp4)
            video_url = self._pick_video_file(video, orientation)
            if not video_url:
                return None

            filename = f"scene_{key_point.index}_{slugify(query[:25])}_broll.mp4"
            local_path = output_dir / filename

            vid_response = self.session.get(video_url, timeout=60)
            vid_response.raise_for_status()
            local_path.write_bytes(vid_response.content)

            logger.info(
                "Downloaded B-roll video: %s (%d KB)",
                filename, len(vid_response.content) // 1024,
            )

            return ImageAsset(
                key_point_index=key_point.index,
                local_path=local_path,
                source_url=video.get("url", ""),
                photographer=video.get("user", {}).get("name", "Unknown"),
                alt_text=query,
                asset_type="video",
            )

        except Exception as e:
            logger.debug("B-roll video search failed for '%s': %s", query, e)
            return None

    async def _async_search_video_broll(
        self,
        session: aiohttp.ClientSession,
        key_point: KeyPoint,
        output_dir: Path,
        orientation: str,
    ) -> Optional[ImageAsset]:
        """Async version of B-roll video search."""
        if not config.USE_VIDEO_BROLL:
            return None

        query = key_point.visual_query
        try:
            params = {
                "query": query,
                "per_page": 5,
                "orientation": orientation,
                "size": "medium",
            }
            async with session.get(self.PEXELS_VIDEO_URL, params=params) as resp:
                data = await resp.json()

            videos = data.get("videos", [])
            if not videos:
                return None

            video = self._select_best_video(videos, orientation)
            if not video:
                return None

            video_url = self._pick_video_file(video, orientation)
            if not video_url:
                return None

            filename = f"scene_{key_point.index}_{slugify(query[:25])}_broll.mp4"
            local_path = output_dir / filename

            async with session.get(video_url) as vid_resp:
                content = await vid_resp.read()
                local_path.write_bytes(content)

            logger.info(
                "Downloaded B-roll video: %s (%d KB) [async]",
                filename, len(content) // 1024,
            )

            return ImageAsset(
                key_point_index=key_point.index,
                local_path=local_path,
                source_url=video.get("url", ""),
                photographer=video.get("user", {}).get("name", "Unknown"),
                alt_text=query,
                asset_type="video",
            )
        except Exception as e:
            logger.debug("Async B-roll search failed for '%s': %s", query, e)
            return None

    @staticmethod
    def _select_best_video(videos: list[dict], orientation: str) -> Optional[dict]:
        """Select the best video: prefer short (5-30s), correct orientation."""
        scored = []
        for video in videos:
            duration = video.get("duration", 0)
            width = video.get("width", 0)
            height = video.get("height", 0)

            # Prefer clips between 5-30 seconds
            if duration < 3 or duration > 60:
                continue

            score = 100
            if 5 <= duration <= 30:
                score += 50

            # Prefer correct orientation
            if orientation == "portrait" and height > width:
                score += 30
            elif orientation == "landscape" and width > height:
                score += 30

            # Prefer higher resolution
            score += min(width * height / 100000, 50)

            scored.append((score, video))

        if not scored:
            return None

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    @staticmethod
    def _pick_video_file(video: dict, orientation: str) -> Optional[str]:
        """Pick the best video file URL (prefer HD mp4)."""
        files = video.get("video_files", [])
        if not files:
            return None

        # Score each file: prefer HD, mp4, correct dimensions
        scored = []
        for f in files:
            file_type = f.get("file_type", "")
            width = f.get("width", 0)
            height = f.get("height", 0)
            quality = f.get("quality", "")

            if "mp4" not in file_type:
                continue

            score = 0
            # Prefer HD but not 4K (too large)
            if quality == "hd":
                score += 50
            elif quality == "sd":
                score += 30

            # Prefer reasonable file size (720p-1080p range)
            pixels = width * height
            if 500000 < pixels < 3000000:
                score += 40
            elif pixels > 0:
                score += 10

            link = f.get("link", "")
            if link:
                scored.append((score, link))

        if not scored:
            return None

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    @staticmethod
    def _format_to_orientation(video_format: str) -> str:
        """Map video format to Pexels orientation parameter."""
        mapping = {
            "vertical": "portrait",
            "horizontal": "landscape",
            "square": "square",
        }
        return mapping.get(video_format, "portrait")
