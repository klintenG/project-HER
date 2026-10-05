"""
Project HER – Publisher Module
Manages the publishing queue and provides multiple publishing strategies:
1. Manual mode – organises files + opens folder for manual upload
2. YouTube API – direct upload via YouTube Data API v3 (free)
3. Browser automation – Playwright-based upload for other platforms (free, experimental)
4. macOS Shortcuts – triggers Shortcuts automations for upload

Also handles scheduling: randomised posting times with jitter.
"""

from __future__ import annotations

import json
import logging
import os
import random
import subprocess
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import config
from automation.metadata_generator import VideoMetadata, PlatformMeta

logger = logging.getLogger(__name__)


# ── Schedule ──────────────────────────────────────────

@dataclass
class ScheduledPost:
    """A single scheduled post for one video on one platform."""
    story_id: str
    platform: str
    video_path: str
    scheduled_time: str             # ISO format
    metadata: dict = field(default_factory=dict)  # PlatformMeta as dict
    status: str = "pending"         # pending | uploading | published | failed
    error: str = ""
    published_url: str = ""


def generate_schedule(
    story_ids: list[str],
    video_paths: list[str],
    metadata_list: list[VideoMetadata],
    platforms: list[str],
    start_hour: int = 17,           # 5 PM — prime time start
    interval_minutes: int = 60,     # ~1 hour between videos
    jitter_minutes: int = 15,       # ± random jitter
) -> list[ScheduledPost]:
    """
    Generate a randomised posting schedule.

    All platforms for one video are posted at the same time.
    Videos are staggered by ~interval_minutes with random jitter.

    Args:
        story_ids: IDs of the stories.
        video_paths: Paths to the rendered .mp4 files.
        metadata_list: VideoMetadata objects with per-platform details.
        platforms: Which platforms to schedule for.
        start_hour: Hour of day (24h) to start posting.
        interval_minutes: Base interval between video posts.
        jitter_minutes: Random jitter ± this many minutes.

    Returns:
        Flat list of ScheduledPost objects.
    """
    now = datetime.now()
    # Start today at start_hour, or tomorrow if it's already past
    start_time = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    if start_time < now:
        start_time += timedelta(days=1)

    schedule = []
    current_time = start_time

    for i, (sid, vpath, meta) in enumerate(zip(story_ids, video_paths, metadata_list)):
        # Add random jitter to this video's post time
        jitter = random.randint(-jitter_minutes, jitter_minutes)
        post_time = current_time + timedelta(minutes=jitter)

        # Don't let jitter push it before the previous post
        if schedule and post_time.isoformat() <= schedule[-1].scheduled_time:
            post_time = datetime.fromisoformat(schedule[-1].scheduled_time) + timedelta(minutes=5)

        for platform in platforms:
            pmeta = meta.platforms.get(platform)
            schedule.append(ScheduledPost(
                story_id=sid,
                platform=platform,
                video_path=str(vpath),
                scheduled_time=post_time.isoformat(),
                metadata=asdict(pmeta) if pmeta else {},
            ))

        # Advance to next slot
        current_time += timedelta(minutes=interval_minutes)

    logger.info(
        "Generated schedule: %d posts across %d videos, starting %s",
        len(schedule), len(story_ids), start_time.strftime("%Y-%m-%d %H:%M"),
    )
    return schedule


# ── Publishing Strategies ─────────────────────────────

class Publisher:
    """
    Manages publishing of videos to social media platforms.
    Supports multiple strategies; falls back gracefully.
    """

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.queue_file = output_dir / "publish_queue.json"

    def save_queue(self, schedule: list[ScheduledPost]):
        """Persist the publishing queue to disk."""
        data = [asdict(s) for s in schedule]
        with open(self.queue_file, "w") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info("Saved publishing queue: %d items → %s", len(data), self.queue_file)

    def load_queue(self) -> list[ScheduledPost]:
        """Load the publishing queue from disk."""
        if not self.queue_file.exists():
            return []
        with open(self.queue_file, "r") as f:
            data = json.load(f)
        return [ScheduledPost(**item) for item in data]

    # ── Strategy: Manual Mode ─────────────────────────

    def prepare_manual_uploads(self, schedule: list[ScheduledPost]) -> Path:
        """
        Organise videos + metadata into per-platform folders for manual upload.
        Creates a README with instructions and the schedule.
        """
        upload_dir = self.output_dir / "upload_ready"
        upload_dir.mkdir(exist_ok=True)

        # Group by video (story_id)
        by_story: dict[str, list[ScheduledPost]] = {}
        for post in schedule:
            by_story.setdefault(post.story_id, []).append(post)

        readme_lines = [
            "# 📱 Upload Schedule",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Total videos: {len(by_story)}",
            "",
            "## Schedule",
            "",
        ]

        for story_id, posts in by_story.items():
            video_path = Path(posts[0].video_path)
            post_time = posts[0].scheduled_time

            # Create per-story folder
            story_dir = upload_dir / story_id
            story_dir.mkdir(exist_ok=True)

            # Symlink or copy the video
            video_link = story_dir / video_path.name
            if not video_link.exists():
                try:
                    video_link.symlink_to(video_path.resolve())
                except OSError:
                    import shutil
                    shutil.copy2(video_path, video_link)

            readme_lines.append(f"### 🎬 {story_id} — Post at {post_time}")
            readme_lines.append(f"Video: `{video_path.name}`")
            readme_lines.append("")

            # Write per-platform metadata files
            for post in posts:
                meta = post.metadata
                platform_file = story_dir / f"{post.platform}.txt"
                with open(platform_file, "w") as f:
                    f.write(f"Platform: {post.platform}\n")
                    f.write(f"Post at: {post.scheduled_time}\n")
                    f.write(f"{'=' * 40}\n\n")
                    f.write(f"TITLE:\n{meta.get('title', '')}\n\n")
                    f.write(f"DESCRIPTION:\n{meta.get('description', '')}\n\n")
                    hashtags = meta.get("hashtags", [])
                    if hashtags:
                        f.write(f"HASHTAGS:\n{' '.join(hashtags)}\n\n")
                    tags = meta.get("tags", [])
                    if tags:
                        f.write(f"TAGS:\n{', '.join(tags)}\n\n")
                    first_comment = meta.get("first_comment", "")
                    if first_comment:
                        f.write(f"FIRST COMMENT:\n{first_comment}\n\n")

                readme_lines.append(f"  - **{post.platform}**: `{platform_file.name}`")

            readme_lines.append("")

        # Write README
        readme_path = upload_dir / "README.md"
        with open(readme_path, "w") as f:
            f.write("\n".join(readme_lines))

        logger.info("Manual upload package ready: %s", upload_dir)
        return upload_dir

    # ── Strategy: macOS Shortcut Trigger ──────────────

    def trigger_macos_shortcut(self, shortcut_name: str, video_path: str, metadata: dict) -> bool:
        """
        Trigger a macOS Shortcut to handle the upload.
        The shortcut receives the video path and metadata as input.

        Setup required:
        1. Create a Shortcut in Shortcuts.app named e.g. "Upload to TikTok"
        2. The shortcut should:
           a. Receive input (file path + text)
           b. Open the platform website/app
           c. Use accessibility actions or simply prompt you to upload

        Args:
            shortcut_name: Name of the macOS Shortcut.
            video_path: Path to the video file.
            metadata: Platform metadata dict.

        Returns:
            True if shortcut was triggered successfully.
        """
        try:
            # Build input for the shortcut
            input_text = json.dumps({
                "video_path": video_path,
                "title": metadata.get("title", ""),
                "description": metadata.get("description", ""),
                "hashtags": metadata.get("hashtags", []),
            })

            result = subprocess.run(
                ["shortcuts", "run", shortcut_name, "--input-path", video_path],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                logger.info("macOS Shortcut '%s' triggered successfully", shortcut_name)
                return True
            else:
                logger.error(
                    "macOS Shortcut '%s' failed: %s", shortcut_name, result.stderr
                )
                return False

        except FileNotFoundError:
            logger.error("'shortcuts' CLI not found — macOS Shortcuts not available")
            return False
        except subprocess.TimeoutExpired:
            logger.warning("macOS Shortcut '%s' timed out", shortcut_name)
            return False
        except Exception as e:
            logger.error("macOS Shortcut error: %s", e)
            return False

    # ── Strategy: Open in Browser (simplest automation) ─

    def open_platform_upload_pages(self, platforms: list[str] | None = None):
        """
        Open the upload pages for each platform in the default browser.
        The human then drags-and-drops the video.
        This is the simplest 'semi-automated' approach.
        """
        urls = {
            "youtube_shorts": "https://studio.youtube.com/channel/UC/videos/upload",
            "tiktok": "https://www.tiktok.com/upload",
            "instagram_reels": "https://www.instagram.com/reels/create/",
            "facebook": "https://www.facebook.com/reels/create",
            "twitter": "https://twitter.com/compose/tweet",
        }
        platforms = platforms or list(urls.keys())

        for p in platforms:
            url = urls.get(p)
            if url:
                try:
                    subprocess.run(["open", url], check=True)
                    logger.info("Opened %s upload page", p)
                except Exception as e:
                    logger.warning("Could not open %s: %s", p, e)

    # ── Strategy: YouTube API (free) ──────────────────

    def upload_to_youtube(
        self,
        video_path: str,
        title: str,
        description: str,
        tags: list[str],
        privacy: str = "public",
        scheduled_time: str = "",
    ) -> Optional[str]:
        """
        Upload a video to YouTube using the Data API v3.

        Requires:
        - YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env
        - One-time OAuth flow (browser login)
        - Token stored in data/youtube_token.json

        Returns:
            YouTube video URL if successful, None if failed.
        """
        try:
            from automation.youtube_uploader import YouTubeUploader
            uploader = YouTubeUploader()
            video_url = uploader.upload(
                video_path=video_path,
                title=title,
                description=description,
                tags=tags,
                privacy=privacy,
                scheduled_time=scheduled_time,
            )
            return video_url
        except ImportError:
            logger.warning("YouTube uploader not configured — install google-auth + google-api-python-client")
            return None
        except Exception as e:
            logger.error("YouTube upload failed: %s", e)
            return None

    # ── Execute Schedule ──────────────────────────────

    def execute_schedule(
        self,
        schedule: list[ScheduledPost],
        strategy: str = "manual",
        dry_run: bool = False,
    ) -> list[ScheduledPost]:
        """
        Execute the publishing schedule using the chosen strategy.

        Args:
            schedule: List of ScheduledPost items.
            strategy: "manual" | "youtube_api" | "macos_shortcuts" | "browser"
            dry_run: If True, just log what would happen.

        Returns:
            Updated schedule with statuses.
        """
        logger.info(
            "Executing schedule: %d posts, strategy=%s, dry_run=%s",
            len(schedule), strategy, dry_run,
        )

        if strategy == "manual":
            upload_dir = self.prepare_manual_uploads(schedule)
            for post in schedule:
                post.status = "ready_for_manual"
            # Open the folder in Finder
            if not dry_run:
                subprocess.run(["open", str(upload_dir)])
            return schedule

        elif strategy == "browser":
            if not dry_run:
                platforms = list(set(p.platform for p in schedule))
                self.open_platform_upload_pages(platforms)
                upload_dir = self.prepare_manual_uploads(schedule)
                subprocess.run(["open", str(upload_dir)])
            for post in schedule:
                post.status = "ready_for_manual"
            return schedule

        elif strategy == "youtube_api":
            for post in schedule:
                if post.platform != "youtube_shorts":
                    post.status = "skipped_not_youtube"
                    continue
                if dry_run:
                    post.status = "dry_run"
                    logger.info("[DRY RUN] Would upload to YouTube: %s", post.metadata.get("title"))
                    continue

                post.status = "uploading"
                url = self.upload_to_youtube(
                    video_path=post.video_path,
                    title=post.metadata.get("title", ""),
                    description=post.metadata.get("description", ""),
                    tags=post.metadata.get("tags", []),
                    scheduled_time=post.scheduled_time,
                )
                if url:
                    post.status = "published"
                    post.published_url = url
                else:
                    post.status = "failed"
                    post.error = "Upload returned None"

            # For non-YouTube platforms, fall back to manual
            non_yt = [p for p in schedule if p.platform != "youtube_shorts"]
            if non_yt:
                self.prepare_manual_uploads(non_yt)

            return schedule

        elif strategy == "macos_shortcuts":
            shortcut_map = {
                "youtube_shorts": "Upload to YouTube",
                "tiktok": "Upload to TikTok",
                "instagram_reels": "Upload to Instagram",
                "facebook": "Upload to Facebook",
                "twitter": "Upload to Twitter",
            }
            for post in schedule:
                shortcut = shortcut_map.get(post.platform)
                if not shortcut:
                    post.status = "skipped_no_shortcut"
                    continue
                if dry_run:
                    post.status = "dry_run"
                    logger.info("[DRY RUN] Would trigger '%s' for %s", shortcut, post.story_id)
                    continue

                post.status = "uploading"
                ok = self.trigger_macos_shortcut(shortcut, post.video_path, post.metadata)
                post.status = "published" if ok else "failed"

            return schedule

        else:
            logger.error("Unknown publishing strategy: %s", strategy)
            return schedule
