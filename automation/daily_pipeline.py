"""
Project HER – Daily Pipeline
Master orchestrator that runs the full daily workflow:
1. Curate stories (Agent 1)
2. Validate stories with feedback loop (Agent 2)
3. Generate videos via existing pipeline
4. Generate metadata (Agent 3)
5. Schedule and publish

Can be run manually (`python -m automation.daily_pipeline`) or triggered
by cron / launchd / APScheduler.
"""

from __future__ import annotations

import json
import logging
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import config as config_module
from automation.story_curator import StoryCuratorAgent, StoryCandidate
from automation.story_validator import StoryValidatorAgent, ValidationResult
from automation.story_history import StoryHistory, StoryRecord
from automation.metadata_generator import MetadataGeneratorAgent, VideoMetadata, PlatformMeta
from automation.publisher import Publisher, generate_schedule, ScheduledPost

logger = logging.getLogger(__name__)


# ── Configuration ─────────────────────────────────────

@dataclass
class DailyConfig:
    """Configuration for a daily pipeline run."""
    target_videos: int = 5                       # how many videos to produce
    max_curation_rounds: int = 5                 # max curator → validator loops
    initial_batch_size: int = 7                  # first batch: request more than needed
    tone: str = "storytelling"                   # narration tone
    renderer: str = "remotion"                   # "remotion" | "moviepy"
    ai_images: bool = True                       # use AI-generated images
    visual_style: str = "claymorphism"           # visual style
    video_format: str = "vertical"               # 9:16 for shorts/reels/tiktok
    platforms: list[str] = field(default_factory=lambda: [
        "youtube_shorts", "tiktok", "instagram_reels", "facebook", "twitter"
    ])
    publish_strategy: str = "manual"             # manual | youtube_api | macos_shortcuts | browser
    start_hour: int = 17                         # 5 PM
    interval_minutes: int = 70                   # ~1h10m between videos
    jitter_minutes: int = 15                     # ± 15 min randomness
    dry_run: bool = False                        # don't actually publish
    max_story_words: int = 130                   # hard cap on story word count for 50-60s videos


# ── Run Report ────────────────────────────────────────

@dataclass
class DailyReport:
    """Summary of a daily pipeline run."""
    date: str = ""
    started_at: str = ""
    finished_at: str = ""
    duration_minutes: float = 0.0
    # Curation
    total_candidates_generated: int = 0
    curation_rounds: int = 0
    stories_approved: int = 0
    stories_rejected: int = 0
    # Video generation
    videos_generated: int = 0
    videos_failed: int = 0
    video_details: list[dict] = field(default_factory=list)
    # Publishing
    posts_scheduled: int = 0
    posts_published: int = 0
    posts_failed: int = 0
    publish_strategy: str = ""
    # Errors
    errors: list[str] = field(default_factory=list)


# ── Pipeline ──────────────────────────────────────────

class DailyPipeline:
    """
    Orchestrates the complete daily content creation and publishing workflow.
    """

    def __init__(
        self,
        config: DailyConfig | None = None,
        llm_provider: str | None = None,
        llm_model: str | None = None,
    ):
        self.config = config or DailyConfig()
        self._provider = llm_provider
        self._model = llm_model

        # Agents
        self.curator = StoryCuratorAgent(provider=llm_provider, model=llm_model)
        self.validator = StoryValidatorAgent(provider=llm_provider, model=llm_model)
        self.meta_gen = MetadataGeneratorAgent(provider=llm_provider, model=llm_model)
        self.history = StoryHistory()

        # Output directory for today's run
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.run_dir = Path(config_module.BASE_DIR) / "data" / "daily_runs" / self.today
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self.publisher = Publisher(self.run_dir)

    def run(self, progress_callback=None) -> DailyReport:
        """
        Execute the full daily pipeline.

        Returns:
            DailyReport with complete summary.
        """
        report = DailyReport(
            date=self.today,
            started_at=datetime.now().isoformat(),
        )
        start_time = time.time()

        def _log(msg: str):
            logger.info(msg)
            if progress_callback:
                try:
                    progress_callback(msg)
                except Exception:
                    pass  # Never let logging crash the pipeline

        try:
            # ── Phase 1: Story Curation + Validation Loop ──
            _log("=" * 60)
            _log(f"🎬 DAILY PIPELINE — {self.today}")
            _log(f"   Target: {self.config.target_videos} videos")
            _log("=" * 60)

            approved_stories = self._curate_and_validate(report, _log)

            if not approved_stories:
                report.errors.append("No stories approved after all curation rounds")
                _log("❌ No stories approved — aborting pipeline")
                return report  # finally will finalize

            # ── Phase 2: Video Generation ──────────────────
            _log(f"\n📹 Generating {len(approved_stories)} videos...")
            video_results = self._generate_videos(approved_stories, report, _log)

            if not video_results:
                report.errors.append("No videos generated successfully")
                _log("❌ No videos generated — aborting pipeline")
                return report  # finally will finalize

            # ── Phase 3: Metadata Generation ───────────────
            _log(f"\n📝 Generating metadata for {len(video_results)} videos...")
            metadata_list = self._generate_metadata(video_results, _log)

            # ── Phase 4: Schedule + Publish ────────────────
            _log(f"\n📅 Scheduling {len(video_results)} videos...")
            self._schedule_and_publish(video_results, metadata_list, report, _log)

        except BaseException as e:
            # BaseException catches SystemExit, KeyboardInterrupt, etc.
            report.errors.append(f"Pipeline crash ({type(e).__name__}): {str(e)}")
            logger.error("Daily pipeline crashed: %s", e, exc_info=True)
            # Re-raise KeyboardInterrupt so the user can actually ctrl-C
            if isinstance(e, KeyboardInterrupt):
                raise

        finally:
            # ALWAYS write the report, even on crash
            self._finalize_report(report, start_time)

        return report

    # ── Phase 1: Curation + Validation Loop ───────────

    def _curate_and_validate(
        self,
        report: DailyReport,
        _log,
    ) -> list[tuple[StoryCandidate, str]]:
        """
        Generate and validate stories until we have enough approved ones.
        Returns list of (StoryCandidate, story_id) tuples.
        """
        target = self.config.target_videos
        max_rounds = self.config.max_curation_rounds

        # Get history for duplicate detection
        history_summary = self.history.summary_for_validator(days=30)
        avoid_titles = self.history.get_recent_titles(days=60)
        avoid_synopses = self.history.get_recent_synopses(days=30)

        approved: list[tuple[StoryCandidate, str]] = []
        feedback = ""
        round_num = 0

        while len(approved) < target and round_num < max_rounds:
            round_num += 1
            need = target - len(approved)
            batch_size = max(need + 2, self.config.initial_batch_size) if round_num == 1 else need + 1

            _log(f"\n🔄 Curation Round {round_num}/{max_rounds} — need {need} more stories")

            # ── Curator: Generate candidates ──
            _log(f"  📖 Curator generating {batch_size} candidates...")
            candidates = self.curator.generate_batch(
                count=batch_size,
                avoid_titles=avoid_titles,
                avoid_synopses=avoid_synopses,
                feedback=feedback,
            )
            report.total_candidates_generated += len(candidates)

            if not candidates:
                _log("  ⚠️  Curator returned 0 candidates — retrying...")
                continue

            _log(f"  📖 Curator produced {len(candidates)} candidates")
            for c in candidates:
                _log(f"     • [{c.genre}] \"{c.title}\"")

            # ── Validator: Review candidates ──
            _log(f"  🔍 Validator reviewing {len(candidates)} candidates...")
            results = self.validator.validate_batch(candidates, history_summary)

            for cand, res in zip(candidates, results):
                if res.approved and len(approved) < target:
                    # Save to history
                    record = StoryRecord(
                        id="",
                        title=cand.title,
                        hook=cand.hook,
                        synopsis=cand.synopsis,
                        moral=cand.moral,
                        genre=cand.genre,
                        tags=cand.tags,
                        full_story=cand.full_story,
                        status="approved",
                        score=res.score,
                    )
                    story_id = self.history.add_story(record)
                    approved.append((cand, story_id))
                    avoid_titles.append(cand.title)
                    avoid_synopses.append(cand.synopsis)
                    report.stories_approved += 1
                    _log(f"  ✅ APPROVED: \"{cand.title}\" (score: {res.score}/10)")
                else:
                    report.stories_rejected += 1
                    _log(f"  ❌ REJECTED: \"{cand.title}\" (score: {res.score}/10) — {res.feedback[:80]}")

            # Build feedback for next round
            if len(approved) < target:
                feedback = self.validator.get_rejection_feedback(results)

        report.curation_rounds = round_num
        _log(f"\n✅ Curation complete: {len(approved)}/{target} stories approved in {round_num} rounds")

        # Save curation report
        curation_data = {
            "rounds": round_num,
            "total_candidates": report.total_candidates_generated,
            "approved": [(c.title, sid) for c, sid in approved],
            "final_count": len(approved),
        }
        with open(self.run_dir / "curation_report.json", "w") as f:
            json.dump(curation_data, f, indent=2)

        return approved

    # ── Phase 2: Video Generation ─────────────────────

    def _generate_videos(
        self,
        approved_stories: list[tuple[StoryCandidate, str]],
        report: DailyReport,
        _log,
    ) -> list[dict]:
        """
        Generate videos for each approved story using our existing pipeline.
        Returns list of {story_id, candidate, video_path, pipeline_result} dicts.
        """
        from agent.orchestrator import AgentOrchestrator

        orchestrator = AgentOrchestrator(
            llm_provider=self._provider,
            llm_model=self._model,
            pexels_api_key=config_module.PEXELS_API_KEY,
        )

        results = []

        for i, (candidate, story_id) in enumerate(approved_stories):
            _log(f"\n  🎥 [{i + 1}/{len(approved_stories)}] Generating video for \"{candidate.title}\"...")
            video_start = time.time()

            try:
                # Output directory for this specific video
                video_dir = self.run_dir / f"video_{story_id}"
                video_dir.mkdir(exist_ok=True)

                # Run the existing pipeline with the story text
                pipeline_result = orchestrator.run(
                    input_source=candidate.full_story,
                    tone=self.config.tone,
                    video_format=self.config.video_format,
                    output_dir=video_dir,
                    ai_images=self.config.ai_images,
                    visual_style=self.config.visual_style,
                    renderer=self.config.renderer,
                )

                elapsed = time.time() - video_start

                if pipeline_result.success and pipeline_result.video_path:
                    results.append({
                        "story_id": story_id,
                        "candidate": candidate,
                        "video_path": str(pipeline_result.video_path),
                        "duration": pipeline_result.duration,
                        "pipeline_result": pipeline_result,
                    })
                    report.videos_generated += 1
                    report.video_details.append({
                        "story_id": story_id,
                        "title": candidate.title,
                        "video_path": str(pipeline_result.video_path),
                        "duration": pipeline_result.duration,
                        "processing_time": elapsed,
                    })
                    _log(f"  ✅ Video done: {pipeline_result.duration:.1f}s, took {elapsed:.1f}s")

                    # Update history with video path
                    self.history.update_story(story_id, video_path=str(pipeline_result.video_path))
                else:
                    report.videos_failed += 1
                    errors = pipeline_result.errors if pipeline_result.errors else ["Unknown error"]
                    report.errors.append(f"Video failed for '{candidate.title}': {errors[0]}")
                    _log(f"  ❌ Video failed: {errors[0][:80]}")

            except Exception as e:
                report.videos_failed += 1
                report.errors.append(f"Video crash for '{candidate.title}': {str(e)}")
                _log(f"  ❌ Video crashed: {str(e)[:80]}")
                logger.error("Video generation failed for '%s': %s", candidate.title, e, exc_info=True)

        return results

    # ── Phase 3: Metadata Generation ──────────────────

    def _generate_metadata(
        self,
        video_results: list[dict],
        _log,
    ) -> list[VideoMetadata]:
        """Generate platform-specific metadata for each video."""
        metadata_list = []

        for vr in video_results:
            candidate: StoryCandidate = vr["candidate"]
            _log(f"  📝 Metadata for \"{candidate.title}\"...")

            try:
                meta = self.meta_gen.generate(
                    story_title=candidate.title,
                    story_synopsis=candidate.synopsis,
                    story_moral=candidate.moral,
                    story_genre=candidate.genre,
                    story_tags=candidate.tags,
                    platforms=self.config.platforms,
                )
                metadata_list.append(meta)

                # Save metadata to disk
                meta_file = self.run_dir / f"metadata_{vr['story_id']}.json"
                meta_dict = {
                    "story_title": meta.story_title,
                    "platforms": {
                        p: asdict(pmeta)
                        for p, pmeta in meta.platforms.items()
                    },
                }
                with open(meta_file, "w") as f:
                    json.dump(meta_dict, f, indent=2)

                # Also update history
                self.history.update_story(
                    vr["story_id"],
                    platform_metadata={p: asdict(pmeta) for p, pmeta in meta.platforms.items()},
                )

                _log(f"  ✅ Metadata ready for {len(meta.platforms)} platforms")

            except Exception as e:
                _log(f"  ⚠️  Metadata failed: {e} — using fallback")
                logger.error("Metadata failed: %s", e, exc_info=True)
                # Fallback
                from automation.metadata_generator import VideoMetadata as VM
                meta = VM(story_title=candidate.title, story_synopsis=candidate.synopsis)
                metadata_list.append(meta)

        return metadata_list

    # ── Phase 4: Schedule + Publish ───────────────────

    def _schedule_and_publish(
        self,
        video_results: list[dict],
        metadata_list: list[VideoMetadata],
        report: DailyReport,
        _log,
    ):
        """Generate a schedule and execute the publishing strategy."""
        story_ids = [vr["story_id"] for vr in video_results]
        video_paths = [vr["video_path"] for vr in video_results]

        # Generate randomised schedule
        schedule = generate_schedule(
            story_ids=story_ids,
            video_paths=video_paths,
            metadata_list=metadata_list,
            platforms=self.config.platforms,
            start_hour=self.config.start_hour,
            interval_minutes=self.config.interval_minutes,
            jitter_minutes=self.config.jitter_minutes,
        )

        report.posts_scheduled = len(schedule)
        report.publish_strategy = self.config.publish_strategy

        # Log the schedule
        _log(f"\n📅 Publishing schedule ({len(schedule)} posts):")
        seen_times = set()
        for post in schedule:
            if post.scheduled_time not in seen_times:
                seen_times.add(post.scheduled_time)
                platforms_at_time = [p.platform for p in schedule if p.scheduled_time == post.scheduled_time]
                _log(f"  📌 {post.scheduled_time} — {', '.join(platforms_at_time)}")

        # Save schedule
        self.publisher.save_queue(schedule)

        # Execute
        _log(f"\n🚀 Publishing with strategy: {self.config.publish_strategy}")
        updated = self.publisher.execute_schedule(
            schedule=schedule,
            strategy=self.config.publish_strategy,
            dry_run=self.config.dry_run,
        )

        # Update report
        for post in updated:
            if post.status == "published":
                report.posts_published += 1
                self.history.mark_published(post.story_id, post.platform, post.video_path)
            elif post.status == "failed":
                report.posts_failed += 1

        # Save updated queue
        self.publisher.save_queue(updated)

    # ── Finalize ──────────────────────────────────────

    def _finalize_report(self, report: DailyReport, start_time: float) -> DailyReport:
        """Write the final report to disk. Must never raise."""
        try:
            report.finished_at = datetime.now().isoformat()
            report.duration_minutes = round((time.time() - start_time) / 60, 1)

            # Save report
            report_file = self.run_dir / "daily_report.json"
            with open(report_file, "w") as f:
                json.dump(asdict(report), f, indent=2, default=str)

            # Log summary
            logger.info("=" * 60)
            logger.info("DAILY PIPELINE COMPLETE")
            logger.info("  Date: %s", report.date)
            logger.info("  Duration: %.1f min", report.duration_minutes)
            logger.info("  Stories: %d approved, %d rejected", report.stories_approved, report.stories_rejected)
            logger.info("  Videos: %d generated, %d failed", report.videos_generated, report.videos_failed)
            logger.info("  Posts: %d scheduled, %d published, %d failed",
                         report.posts_scheduled, report.posts_published, report.posts_failed)
            if report.errors:
                logger.warning("  Errors: %d", len(report.errors))
                for err in report.errors:
                    logger.warning("    - %s", err[:120])
            logger.info("  Report: %s", report_file)
            logger.info("=" * 60)
        except Exception as e:
            # Last resort: at least try to dump something
            logger.error("Failed to write daily report: %s", e)
            try:
                emergency_file = self.run_dir / "daily_report_emergency.json"
                with open(emergency_file, "w") as f:
                    json.dump({
                        "date": report.date,
                        "errors": report.errors,
                        "crash": str(e),
                    }, f, indent=2)
            except Exception:
                pass

        return report


# ── CLI Entry Point ───────────────────────────────────

def main():
    """Run the daily pipeline from the command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Project HER — Daily Video Pipeline")
    parser.add_argument("--videos", type=int, default=5, help="Number of videos to generate (default: 5)")
    parser.add_argument("--tone", default="storytelling", help="Narration tone")
    parser.add_argument("--renderer", default="remotion", choices=["remotion", "moviepy"])
    parser.add_argument("--publish", default="manual",
                        choices=["manual", "youtube_api", "macos_shortcuts", "browser"],
                        help="Publishing strategy")
    parser.add_argument("--start-hour", type=int, default=17, help="Start posting at this hour (24h)")
    parser.add_argument("--interval", type=int, default=70, help="Minutes between video posts")
    parser.add_argument("--jitter", type=int, default=15, help="Random jitter ± minutes")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually publish")
    parser.add_argument("--platforms", nargs="+",
                        default=["youtube_shorts", "tiktok", "instagram_reels", "facebook", "twitter"],
                        help="Platforms to publish to")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s │ %(name)-20s │ %(levelname)-7s │ %(message)s",
        datefmt="%H:%M:%S",
    )

    cfg = DailyConfig(
        target_videos=args.videos,
        tone=args.tone,
        renderer=args.renderer,
        publish_strategy=args.publish,
        start_hour=args.start_hour,
        interval_minutes=args.interval,
        jitter_minutes=args.jitter,
        dry_run=args.dry_run,
        platforms=args.platforms,
    )

    pipeline = DailyPipeline(config=cfg)
    report = pipeline.run()

    print(f"\n{'=' * 60}")
    print(f"✅ Daily pipeline finished in {report.duration_minutes:.1f} minutes")
    print(f"   📖 Stories: {report.stories_approved} approved")
    print(f"   🎥 Videos:  {report.videos_generated} generated")
    print(f"   📅 Posts:   {report.posts_scheduled} scheduled")
    if report.errors:
        print(f"   ⚠️  Errors:  {len(report.errors)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
