"""
Project HER v2.0 – Agent Orchestrator
Coordinates the full pipeline with v2.0 enhancements:
scrape → analyze (with hooks) → visuals (async) → narrate (word-level) → compose (themed + BGM)

Phase 6 enhancements:
- Progress callback system for CLI bars & Web UI SSE
- Scrape + analysis result caching
- Stage-level error recovery with retry
- Output metadata JSON manifest

Phase 7 enhancements:
- Content Modes: article, thought_experiment, ghost_collab
- Series/Chain mode with cliffhanger continuity
- Dual-voice narration for Ghost Collaboration
- Question-based pipeline (no scraping needed for thought_experiment/ghost_collab)
"""

from __future__ import annotations
from agent.story_opening import with_story_opening

import json
import logging
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

import config
from agent.scraper import ArticleScraper, ArticleData
from agent.analyzer import ContentAnalyzer, AnalysisResult
from agent.visuals import VisualFinder, ImageAsset
from agent.narration import NarrationEngine, NarrationClip
from agent.compositor import VideoCompositor
from agent.story_splitter import StorySplitter, StoryScreenplay
from agent.ai_visuals import AIImageGenerator, AIImageAsset
from agent.clay_compositor import ClayCompositor
from agent.effects_agent import generate_effects_plan, VideoEffectsPlan
from agent.remotion_renderer import RemotionRenderer
from utils.helpers import slugify, ensure_dir
from utils.progress import ProgressTracker, ProgressCallback
from utils.cache import get_cache, set_cache

# ── Enhanced pipeline imports ──
from agent.elevenlabs_tts import ElevenLabsTTS, ElevenLabsClip
from agent.google_tts import GoogleTTS, GoogleTTSClip
from agent.audio_utils import append_silence_to_audio, generate_whoosh_sfx

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of the full article-to-video pipeline."""
    success: bool = False
    video_path: Optional[Path] = None
    srt_path: Optional[Path] = None
    thumbnail_path: Optional[Path] = None
    duration: float = 0.0
    resolution: str = ""
    video_format: str = ""
    title: str = ""
    key_point_count: int = 0
    processing_time: float = 0.0
    hook: str = ""
    content_type: str = ""
    mood: str = ""
    theme: str = ""
    caption_style: str = ""
    errors: list[str] = field(default_factory=list)
    news_details: dict = field(default_factory=dict)


class AgentOrchestrator:
    """
    Main orchestrator that runs the full article-to-video pipeline.
    
    v2.0 Pipeline stages:
    1. SCRAPE  – Extract article content from URL or raw text
    2. ANALYZE – Use LLM to extract key points, hook, content type, mood
    3. VISUALS – Find and download images (parallel async)
    4. NARRATE – Generate TTS audio with word-level timestamps
    5. COMPOSE – Assemble video with themes, animated captions, BGM, transitions
    """

    def __init__(
        self,
        groq_api_key: Optional[str] = None,
        pexels_api_key: Optional[str] = None,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
    ):
        self.scraper = ArticleScraper()
        self.analyzer = ContentAnalyzer(provider=llm_provider, model=llm_model)
        self._pexels_api_key = pexels_api_key
        self._visual_finder = None
        self.narration_engine = NarrationEngine()
        self._llm_provider = llm_provider
        self._llm_model = llm_model

    @property
    def visual_finder(self):
        # Stock credentials are needed only when the stock branch is actually used.
        if self._visual_finder is None:
            self._visual_finder = VisualFinder(api_key=self._pexels_api_key)
        return self._visual_finder

    @with_story_opening
    def run(
        self,
        input_source: str,
        tone: str = "informative",
        video_format: str = "vertical",
        voice: Optional[str] = None,
        output_dir: Optional[Path] = None,
        num_points: Optional[int] = None,
        include_subtitles: bool = True,
        theme: str = "cinematic",
        caption_style: str = "karaoke",
        transition: str = "fade",
        color_grade: str = "none",
        progress_callback: Optional[ProgressCallback] = None,
        ai_images: bool = False,
        brand_text: str = "",
        platform: str = "",
        visual_style: str = "",
        # ── Content Mode params ──
        content_mode: str = "article",
        question: str = "",
        character_name: str = "",
        modern_topic: str = "",
        voice_pair: str = "default",
        # ── Series params ──
        series_id: str = "",
        episode_number: int = 0,
        # ── Deep Dive params ──
        deep_dive_sources: Optional[list[str]] = None,
        deep_dive_text: str = "",
        # ── Renderer selection ──
        renderer: str = "remotion",  # "remotion" | "moviepy"
        # ── Duration control ──
        target_duration: int = 0,  # 0 = auto, else seconds
        news_source_policy: str = "auto",
        language: str = "english",
        tts_provider: Optional[str] = None,
        speed: str = "+0%",
        quality: str = "high",
        news_music: Optional[bool] = None,
        news_music_path: Optional[str] = None,
        visual_preset: str = "default",
        editorial_text: str = "editorial",
        editorial_assets: str = "auto",
        local_assets: Optional[str] = None,
        autopilot_hook: str = "",
        autopilot_scene_validator=None,
        autopilot_image_generator=None,
        autopilot_story_id: str = "",
    ) -> PipelineResult:
        """
        Execute the full article-to-video pipeline with all v2.0 enhancements.

        Args:
            input_source: URL or raw article text.
            tone: Content tone.
            video_format: Video format ("vertical", "horizontal", "square").
            voice: TTS voice name.
            output_dir: Custom output directory.
            num_points: Override number of key points (3-6).
            include_subtitles: Whether to include animated captions.
            theme: Visual theme preset.
            caption_style: Caption animation style.
            transition: Transition effect type.
            color_grade: Color grading preset name.
            progress_callback: Optional callback for real-time progress updates.

        Returns:
            PipelineResult with output paths and metadata.
        """
        if visual_preset == "reference_editorial" and content_mode in ("article", "story", "topic"):
            from agent.editorial.pipeline import run_editorial
            from agent.news_script import NewsLLM
            return run_editorial(input_source,output_dir=output_dir,
                source_policy="supplied" if content_mode=="story" else news_source_policy,
                tone=tone,language=language,target_duration=target_duration,video_format=video_format,
                renderer=renderer,voice=voice,tts_provider=tts_provider,speed=speed,quality=quality,
                brand_text=brand_text,progress_callback=progress_callback,music=news_music,music_path=news_music_path,
                llm=NewsLLM(self._llm_provider,self._llm_model),subtitle_mode=editorial_text,
                asset_mode=editorial_assets,local_assets=local_assets,
                autopilot_hook=autopilot_hook,autopilot_scene_validator=autopilot_scene_validator,
                image_generator=autopilot_image_generator,autopilot_story_id=autopilot_story_id)
        if visual_preset == "reference_editorial" and content_mode != "news":
            return PipelineResult(errors=["reference_editorial supports article, topic, story and News inputs."])
        if content_mode == "news":
            from agent.news_pipeline import run_news
            from agent.news_script import NewsLLM
            return run_news(input_source, output_dir=output_dir, source_policy=news_source_policy,
                tone=tone, language=language, target_duration=target_duration, video_format=video_format,
                renderer=renderer, voice=voice, tts_provider=tts_provider, speed=speed, quality=quality,
                brand_text=brand_text, progress_callback=progress_callback, music=news_music, music_path=news_music_path,
                llm=NewsLLM(self._llm_provider, self._llm_model),visual_preset=visual_preset,subtitle_mode=editorial_text,
                asset_mode=editorial_assets,local_assets=local_assets)
        start_time = time.time()
        result = PipelineResult()
        tracker = ProgressTracker(callback=progress_callback)

        # Setup output directory
        if output_dir is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_dir = config.OUTPUT_DIR / f"video_{timestamp}"
        ensure_dir(output_dir)

        # Setup voice
        if voice and voice in config.AVAILABLE_VOICES:
            self.narration_engine.voice = config.AVAILABLE_VOICES[voice]
        elif voice:
            self.narration_engine.voice = voice

        # ── Branch: AI Image (Claymorphism) pipeline ──────
        if ai_images or config.AI_IMAGES_ENABLED:
            return self._run_ai_image_pipeline(
                input_source=input_source,
                tone=tone,
                video_format=video_format,
                output_dir=output_dir,
                include_subtitles=include_subtitles,
                transition=transition,
                color_grade=color_grade,
                tracker=tracker,
                start_time=start_time,
                brand_text=brand_text,
                platform=platform,
                visual_style=visual_style,
                content_mode=content_mode,
                question=question,
                character_name=character_name,
                modern_topic=modern_topic,
                voice_pair=voice_pair,
                series_id=series_id,
                episode_number=episode_number,
                deep_dive_sources=deep_dive_sources,
                deep_dive_text=deep_dive_text,
                autopilot_hook=autopilot_hook,
                autopilot_scene_validator=autopilot_scene_validator,
                renderer=renderer,
                target_duration=target_duration,
            )

        try:
            # ── Stage 1: SCRAPE ────────────────────────────
            tracker.start_stage("scrape", "Scraping article...")
            article = self._run_stage_with_retry(
                "scrape",
                lambda: self.scraper.scrape(input_source),
                tracker,
            )
            tracker.complete_stage(
                "scrape",
                f"Scraped: '{article.title}' ({article.word_count} words)",
            )

            is_url = self.scraper._is_url(input_source)
            if is_url and article.word_count < 25:
                raise ValueError(
                    f"Could not extract sufficient text from URL ({article.word_count} words). "
                    "Please check the URL or paste the article content directly."
                )
            elif not is_url and article.word_count < 3:
                raise ValueError("Please provide a topic, script, or article with at least 3 words.")

            # ── Stage 2: ANALYZE (with cache) ──────────────
            tracker.start_stage("analyze", "Analyzing content with AI...")

            cache_content = f"{input_source}|{tone}|{num_points}|{config.LLM_PROVIDER}"
            cached_analysis = get_cache("analysis", cache_content)

            if cached_analysis:
                analysis = self._dict_to_analysis(cached_analysis)
                logger.info("Using cached analysis (%d key points)", len(analysis.key_points))
            else:
                analysis = self._run_stage_with_retry(
                    "analyze",
                    lambda: self.analyzer.analyze(article, tone=tone, num_points=num_points),
                    tracker,
                )
                # Cache the analysis result
                set_cache("analysis", cache_content, self._analysis_to_dict(analysis))

            tracker.update_stage("analyze", progress=0.8, detail=f"{len(analysis.key_points)} key points")
            logger.info(
                "Analysis complete: %d key points, hook='%s', type=%s, mood=%s",
                len(analysis.key_points),
                analysis.hook[:40] if analysis.hook else "none",
                analysis.content_type,
                analysis.mood,
            )
            for kp in analysis.key_points:
                logger.info("  [%d] %s (%s)", kp.index, kp.headline, kp.emotion)
            tracker.complete_stage("analyze", f"{len(analysis.key_points)} key points extracted")

            # ── Stage 3: VISUALS (async) ───────────────────
            tracker.start_stage("visuals", "Finding visual assets...")
            images = self._run_stage_with_retry(
                "visuals",
                lambda: self.visual_finder.find_images(
                    analysis.key_points, output_dir, video_format,
                    theme=theme,
                ),
                tracker,
            )
            tracker.complete_stage("visuals", f"{len(images)} assets downloaded")

            # ── Stage 4: NARRATION (word-level) ────────────
            tracker.start_stage("narrate", "Generating narration...")
            tts_provider = getattr(config, "TTS_PROVIDER", "google_tts")
            if tts_provider == "google_tts":
                try:
                    tts_engine = GoogleTTS(mood=analysis.mood or "neutral")
                    enhanced_clips = self._run_stage_with_retry(
                        "narrate",
                        lambda: tts_engine.generate_narration(
                            analysis.key_points, output_dir,
                        ),
                        tracker,
                    )
                    narrations = [
                        NarrationClip(
                            key_point_index=c.index,
                            audio_path=c.audio_path,
                            duration=c.duration,
                            word_timings=c.word_timings,
                            subtitle_data=c.subtitle_data,
                            speaker=getattr(c, "speaker", ""),
                        )
                        for c in enhanced_clips
                    ]
                except Exception as tts_err:
                    logger.warning("Google TTS failed in standard pipeline, falling back to edge-tts: %s", tts_err)
                    narrations = self._run_stage_with_retry(
                        "narrate",
                        lambda: self.narration_engine.generate_narration(
                            analysis.key_points, output_dir
                        ),
                        tracker,
                    )
            elif tts_provider == "elevenlabs":
                try:
                    tts_engine = ElevenLabsTTS(mood=analysis.mood or "neutral")
                    enhanced_clips = self._run_stage_with_retry(
                        "narrate",
                        lambda: tts_engine.generate_narration(
                            analysis.key_points, output_dir,
                        ),
                        tracker,
                    )
                    narrations = [
                        NarrationClip(
                            key_point_index=c.index,
                            audio_path=c.audio_path,
                            duration=c.duration,
                            word_timings=c.word_timings,
                            subtitle_data=c.subtitle_data,
                            speaker=getattr(c, "speaker", ""),
                        )
                        for c in enhanced_clips
                    ]
                except Exception as tts_err:
                    logger.warning("ElevenLabs TTS failed, falling back to edge-tts: %s", tts_err)
                    narrations = self._run_stage_with_retry(
                        "narrate",
                        lambda: self.narration_engine.generate_narration(
                            analysis.key_points, output_dir
                        ),
                        tracker,
                    )
            else:
                narrations = self._run_stage_with_retry(
                    "narrate",
                    lambda: self.narration_engine.generate_narration(
                        analysis.key_points, output_dir
                    ),
                    tracker,
                )

            # Update key point durations
            for narration in narrations:
                for kp in analysis.key_points:
                    if kp.index == narration.key_point_index:
                        kp.duration = narration.duration

            total_narration = sum(n.duration for n in narrations)
            total_words_timed = sum(len(n.word_timings) for n in narrations)
            logger.info(
                "Narration generated: %.1fs total, %d words timed, %d clips",
                total_narration, total_words_timed, len(narrations),
            )
            tracker.complete_stage("narrate", f"{total_narration:.1f}s narration generated")

            # ── Duration Check (soft guidance) ─────────────
            # Only try to adjust if duration is WAY too short (below minimum).
            # If too long, we preserve the full story — completeness wins.
            min_dur, max_dur = config.TARGET_DURATION
            if total_narration < min_dur:
                logger.warning(
                    "Duration %.1fs is below minimum (%ds). Attempting adjustment...",
                    total_narration, min_dur,
                )
                adjusted = self._enforce_duration(
                    article=article,
                    tone=tone,
                    video_format=video_format,
                    output_dir=output_dir,
                    current_points=len(analysis.key_points),
                    current_duration=total_narration,
                    analysis=analysis,
                    theme=theme,
                )
                if adjusted is not None:
                    analysis, narrations, images = adjusted
                    total_narration = sum(n.duration for n in narrations)
                    logger.info(
                        "After adjustment: %.1fs total, %d key points",
                        total_narration, len(analysis.key_points),
                    )

                    # Refresh key point durations
                    for narration in narrations:
                        for kp in analysis.key_points:
                            if kp.index == narration.key_point_index:
                                kp.duration = narration.duration

            # ── Stage 5: COMPOSE (themed + BGM + captions) ─
            tracker.start_stage("compose", "Composing video...")

            compositor = VideoCompositor(
                video_format=video_format,
                theme=theme,
                caption_style=caption_style,
                transition=transition,
            )

            video_filename = f"{slugify(analysis.title)}.mp4"
            compose_result = self._run_stage_with_retry(
                "compose",
                lambda: compositor.compose(
                    title=analysis.title,
                    key_points=analysis.key_points,
                    images=images,
                    narrations=narrations,
                    output_dir=output_dir,
                    output_filename=video_filename,
                    include_subtitles=include_subtitles,
                    tone=tone,
                    hook_text=analysis.hook,
                    cta_text=analysis.cta,
                    color_grade=color_grade,
                ),
                tracker,
                max_retries=1,  # composing is expensive, only 1 retry
            )

            # ── Build Result ───────────────────────────────
            elapsed = time.time() - start_time
            (output_dir / 'opening-assets.json').write_text(json.dumps([
                {'path':str(Path(image.local_path).resolve()),'subject':getattr(image,'query','') or getattr(image,'prompt',''),'role':'object'}
                for image in images if Path(image.local_path).is_file()],default=str))
            result.success = True
            result.video_path = compose_result["video_path"]
            result.srt_path = compose_result.get("srt_path")
            result.thumbnail_path = compose_result.get("thumbnail_path")
            result.duration = compose_result["duration"]
            result.resolution = compose_result["resolution"]
            result.video_format = video_format
            result.title = analysis.title
            result.key_point_count = len(analysis.key_points)
            result.processing_time = elapsed
            result.hook = analysis.hook
            result.content_type = analysis.content_type
            result.mood = analysis.mood
            result.theme = theme
            result.caption_style = caption_style

            tracker.complete_stage("compose", f"Video rendered ({result.duration:.1f}s)")

            logger.info("=" * 60)
            logger.info("PIPELINE COMPLETE")
            logger.info("  Video: %s", result.video_path)
            logger.info("  Duration: %.1fs", result.duration)
            logger.info("  Resolution: %s", result.resolution)
            logger.info("  Theme: %s | Captions: %s", theme, caption_style)
            logger.info("  Hook: %s", result.hook)
            logger.info("  Processing time: %.1fs", elapsed)
            logger.info("=" * 60)

            # ── Save metadata manifest ─────────────────────
            self._save_manifest(result, output_dir, {
                "input_source": input_source[:200],
                "tone": tone,
                "video_format": video_format,
                "theme": theme,
                "caption_style": caption_style,
                "transition": transition,
                "color_grade": color_grade,
                "voice": self.narration_engine.voice,
                "voice_speed": config.VOICE_SPEED,
                "include_subtitles": include_subtitles,
                "num_points_requested": num_points,
                "key_points": [
                    {"index": kp.index, "headline": kp.headline, "emotion": kp.emotion}
                    for kp in analysis.key_points
                ],
            })

        except Exception as e:
            elapsed = time.time() - start_time
            result.processing_time = elapsed
            result.errors.append(str(e))
            logger.error("Pipeline failed after %.1fs: %s", elapsed, e, exc_info=True)
            # Mark running stages as failed
            for stage in tracker.stages.values():
                if stage.status == "running":
                    tracker.fail_stage(stage.name, str(e))

        return result

    # ── AI Image (Claymorphism) Pipeline ──────────────

    def _run_ai_image_pipeline(
        self,
        input_source: str,
        tone: str,
        video_format: str,
        output_dir: Path,
        include_subtitles: bool,
        transition: str,
        color_grade: str,
        tracker: ProgressTracker,
        start_time: float,
        brand_text: str = "",
        visual_style: str = "",
        # ── Content Mode params ──
        content_mode: str = "article",
        question: str = "",
        character_name: str = "",
        modern_topic: str = "",
        voice_pair: str = "default",
        # ── Series params ──
        series_id: str = "",
        episode_number: int = 0,
        # ── Deep Dive params ──
        deep_dive_sources: Optional[list[str]] = None,
        deep_dive_text: str = "",
        # ── Renderer selection ──
        renderer: str = "remotion",
        # ── Duration control ──
        target_duration: int = 0,
        **kwargs,
    ) -> PipelineResult:
        """
        Complete AI-image pipeline with visual styles.
        
        Content modes:
        - article: SCRAPE → SPLIT → AI_VISUALS → NARRATE → COMPOSE
        - thought_experiment: SPLIT → AI_VISUALS → NARRATE → COMPOSE (no scraping)
        - ghost_collab: SPLIT → AI_VISUALS → DUAL_NARRATE → COMPOSE (no scraping, two voices)
        - deep_dive: MULTI_SCRAPE → MULTI_PASS_SPLIT → AI_VISUALS → DUAL_NARRATE → COMPOSE
        """
        from agent.analyzer import KeyPoint

        result = PipelineResult()

        # ── Duration target (soft guidance) ────────────────
        # Duration is a SOFT target. Story completeness always wins.
        # We store the original config and set a generous range so the
        # post-narration check only warns (doesn't cut) unless grossly over.
        original_target_duration = config.TARGET_DURATION
        if target_duration and target_duration > 0:
            # Very generous range: allow up to 2x the target before even logging a warning
            config.TARGET_DURATION = (
                max(10, target_duration - 15),
                int(target_duration * 2),  # 2x — story completeness is king
            )
            logger.info(
                "Duration soft target: user=%ds → config range=(%d, %d)",
                target_duration, config.TARGET_DURATION[0], config.TARGET_DURATION[1],
            )

        # ── Series context loading ─────────────────────
        previous_cliffhanger = ""
        if series_id:
            series_context = self._load_series_context(series_id)
            if series_context and episode_number > 1:
                previous_cliffhanger = series_context.get("last_cliffhanger", "")
                if not episode_number:
                    episode_number = series_context.get("next_episode", 1)
                logger.info(
                    "Series '%s' ep %d — previous cliffhanger: %s",
                    series_id, episode_number, previous_cliffhanger[:60],
                )

        try:
            # ── Stage 1: SCRAPE or PREPARE INPUT ───────────
            if content_mode == "deep_dive":
                # Multi-source scraping for Deep Dive mode
                tracker.start_stage("scrape", "Scraping multiple sources for Deep Dive...")
                sources = deep_dive_sources or []
                if deep_dive_text:
                    sources.append(deep_dive_text)
                if not sources and input_source:
                    sources = [input_source]

                if len(sources) > 1:
                    article = self._run_stage_with_retry(
                        "scrape",
                        lambda: self.scraper.scrape_multiple(sources),
                        tracker,
                    )
                else:
                    article = self._run_stage_with_retry(
                        "scrape",
                        lambda: self.scraper.scrape(sources[0] if sources else input_source),
                        tracker,
                    )
                tracker.complete_stage(
                    "scrape",
                    f"Deep Dive: {article.word_count} words from {len(sources)} source(s)",
                )
            elif content_mode in ("thought_experiment", "ghost_collab"):
                # No scraping needed — build ArticleData from question/topic
                tracker.start_stage("scrape", f"Preparing {content_mode.replace('_', ' ')} input...")
                
                if content_mode == "thought_experiment":
                    synth_title = question[:80] if question else "Thought Experiment"
                    synth_text = (
                        f"Question: {question}\n\n"
                        f"This is a thought experiment exploring the philosophical and practical "
                        f"implications of: {question}"
                    )
                else:  # ghost_collab
                    synth_title = f"Conversation with {character_name}" if character_name else "Ghost Collaboration"
                    synth_text = (
                        f"A simulated dialogue between a modern narrator and {character_name or 'a historical figure'}.\n\n"
                        f"Topic: {modern_topic or question or 'a fascinating discussion'}\n\n"
                        f"The narrator presents modern concepts and the character responds with their "
                        f"unique historical perspective."
                    )
                
                article = ArticleData(
                    title=synth_title,
                    text=synth_text,
                    source_url="",
                    word_count=len(synth_text.split()),
                )
                tracker.complete_stage("scrape", f"Input prepared: '{synth_title}'")
            else:
                # Standard article scraping
                tracker.start_stage("scrape", "Scraping article...")
                article = self._run_stage_with_retry(
                    "scrape",
                    lambda: self.scraper.scrape(input_source),
                    tracker,
                )
                tracker.complete_stage(
                    "scrape",
                    f"Scraped: '{article.title}' ({article.word_count} words)",
                )

                is_url = self.scraper._is_url(input_source)
                if is_url and article.word_count < 25:
                    raise ValueError(
                        f"Could not extract sufficient text from URL ({article.word_count} words). "
                        "Please check the URL or paste the article content directly."
                    )
                elif not is_url and article.word_count < 3:
                    raise ValueError("Please provide a topic, script, or article with at least 3 words.")

            # ── Stage 2: SPLIT (AI story → screens) ───────
            tracker.start_stage("analyze", "Splitting story into screens...")
            splitter = StorySplitter(provider=self._llm_provider, model=self._llm_model)

            screenplay = self._run_stage_with_retry(
                "analyze",
                lambda: splitter.split(
                    text=article.text,
                    title=article.title,
                    tone=tone,
                    brand_text=brand_text,
                    content_mode=content_mode,
                    question=question,
                    character_name=character_name,
                    modern_topic=modern_topic,
                    series_id=series_id,
                    episode_number=episode_number,
                    previous_cliffhanger=previous_cliffhanger,
                    target_duration=target_duration,
                ),
                tracker,
            )

            logger.info(
                "Story split: %d screens, hook='%s', mood=%s",
                len(screenplay.screens),
                screenplay.hook[:40] if screenplay.hook else "none",
                screenplay.mood,
            )
            for s in screenplay.screens:
                logger.info(
                    "  [%d] %s | %s | %.1fs",
                    s.index, s.visual_type, s.text[:50], s.duration,
                )

            # ── Post-process: Force 100% image coverage ────
            # Convert any remaining text_only screens to image screens.
            # Every second of video should have a background image.
            is_enhanced = (
                content_mode != "kids_story"
                and getattr(config, "ENHANCED_PIPELINE", False)
            )

            text_only_converted = 0
            for s in screenplay.screens:
                if s.visual_type == "text_only":
                    s.visual_type = "image"
                    # Auto-generate an image prompt from the screen text
                    if not s.image_prompt:
                        snippet = s.text[:120].strip()
                        if is_enhanced:
                            # Better auto-prompt: cinematic + specific visual cues
                            s.image_prompt = (
                                f"Cinematic wide shot, dramatic lighting, "
                                f"photorealistic scene illustrating: {snippet}"
                            )
                        else:
                            s.image_prompt = f"Atmospheric cinematic scene: {snippet}"
                    s.scene_type = "B"  # Convert to narrative+image scene
                    text_only_converted += 1
                    logger.info(
                        "  [%d] Converted text_only → image (prompt: %s)",
                        s.index, s.image_prompt[:60],
                    )
            if text_only_converted:
                logger.info(
                    "Converted %d text_only screens to image for full visual coverage",
                    text_only_converted,
                )

            # ── Character consistency: anchor descriptions ──
            # For enhanced pipeline, extract character/subject descriptions
            # from the first non-intro screen's image_prompt and prepend
            # to all subsequent image prompts for visual consistency.
            if is_enhanced and getattr(config, "ENHANCED_CHAR_CONSISTENCY", False):
                anchor_prompt = ""
                for s in screenplay.screens:
                    if not s.is_intro and not s.is_outro and s.image_prompt:
                        anchor_prompt = s.image_prompt
                        break

                if anchor_prompt:
                    # Extract visual subject cues (first 80 chars typically
                    # contain the subject/character description)
                    anchor_snippet = anchor_prompt[:100]
                    applied = 0
                    for s in screenplay.screens:
                        if s.is_intro or s.is_outro or not s.image_prompt:
                            continue
                        # Skip the anchor screen itself
                        if s.image_prompt == anchor_prompt:
                            continue
                        # Prepend consistency anchor if not already present
                        if anchor_snippet[:40] not in s.image_prompt:
                            s.image_prompt = (
                                f"Same visual style and characters as: {anchor_snippet}. "
                                f"{s.image_prompt}"
                            )
                            applied += 1
                    if applied:
                        logger.info(
                            "Character consistency: anchored %d screens to '%s'",
                            applied, anchor_snippet[:50],
                        )

            tracker.complete_stage(
                "analyze",
                f"{len(screenplay.screens)} screen segments created",
            )

            if kwargs.get("autopilot_scene_validator"):
                screenplay.screens = [s for s in screenplay.screens if not s.is_intro and not s.is_outro]
                if not screenplay.screens:
                    raise ValueError("Autopilot requires narrated story scenes")
                kwargs["autopilot_scene_validator"](screenplay)

            # ── Stage 3: AI VISUALS (Pollinations) ────────
            tracker.start_stage("visuals", "Generating AI images...")
            portrait_mode = (
                is_enhanced
                and getattr(config, "ENHANCED_IMAGE_PORTRAIT", False)
            )
            generator = AIImageGenerator(
                visual_style=visual_style,
                portrait_mode=portrait_mode,
            )

            images = self._run_stage_with_retry(
                "visuals",
                lambda: generator.generate_images(
                    screenplay.screens, output_dir,
                ),
                tracker,
            )
            tracker.complete_stage(
                "visuals",
                f"{len(images)} AI images generated",
            )

            # ── Stage 4: NARRATION ─────────────────────────
            tracker.start_stage("narrate", "Generating narration...")

            if content_mode == "ghost_collab":
                # Dual-voice narration for dialogue
                narrations = self._run_stage_with_retry(
                    "narrate",
                    lambda: self.narration_engine.generate_dialogue_narration(
                        screens=screenplay.screens,
                        output_dir=output_dir,
                        voice_pair_name=voice_pair,
                    ),
                    tracker,
                )
            elif content_mode == "deep_dive":
                # Dual-voice narration for Deep Dive podcast conversation
                # Map host_a/host_b speakers to narrator/character for the narration engine
                dd_voice_cfg = config.DEEP_DIVE_VOICES.get(voice_pair, config.DEEP_DIVE_VOICES["default"])
                for s in screenplay.screens:
                    if s.speaker == "host_a":
                        s.speaker = "narrator"
                    elif s.speaker == "host_b":
                        s.speaker = "character"
                    # Set character_name for display (optional)
                    if not s.character_name and s.speaker == "character":
                        s.character_name = "Host B"

                # Create a temporary ghost_collab voice config for the narration engine
                _original_voices = config.GHOST_COLLAB_VOICES.get("_deep_dive_temp")
                config.GHOST_COLLAB_VOICES["_deep_dive_temp"] = {
                    "narrator": dd_voice_cfg["host_a"],
                    "character": dd_voice_cfg["host_b"],
                }
                try:
                    narrations = self._run_stage_with_retry(
                        "narrate",
                        lambda: self.narration_engine.generate_dialogue_narration(
                            screens=screenplay.screens,
                            output_dir=output_dir,
                            voice_pair_name="_deep_dive_temp",
                        ),
                        tracker,
                    )
                finally:
                    # Cleanup temp voice config
                    config.GHOST_COLLAB_VOICES.pop("_deep_dive_temp", None)
            elif is_enhanced and getattr(config, "TTS_PROVIDER", "") in ("elevenlabs", "replicate", "google_tts"):
                # ── Enhanced TTS: ElevenLabs, Google AI Studio, or Replicate ──
                tts_provider = config.TTS_PROVIDER
                logger.info("Using %s TTS (enhanced pipeline)", tts_provider)
                narration_key_points = [
                    KeyPoint(
                        index=screen.index,
                        headline=screen.text[:60],
                        narration=screen.text,
                        visual_query=screen.image_prompt or screen.text[:40],
                        duration=screen.duration,
                        emotion=screen.emotion,
                    )
                    for screen in screenplay.screens
                    if not screen.is_intro and not screen.is_outro
                ]

                try:
                    if tts_provider == "replicate":
                        from agent.replicate_tts import ReplicateTTS
                        tts_engine = ReplicateTTS(mood=screenplay.mood or "neutral")
                    elif tts_provider == "google_tts":
                        tts_engine = GoogleTTS(mood=screenplay.mood or "neutral")
                    else:
                        tts_engine = ElevenLabsTTS(mood=screenplay.mood or "neutral")

                    enhanced_clips = self._run_stage_with_retry(
                        "narrate",
                        lambda: tts_engine.generate_narration(
                            narration_key_points, output_dir,
                        ),
                        tracker,
                    )
                    # Convert to NarrationClip for downstream compat
                    narrations = [
                        NarrationClip(
                            key_point_index=c.index,
                            audio_path=c.audio_path,
                            duration=c.duration,
                            word_timings=c.word_timings,
                            subtitle_data=c.subtitle_data,
                            speaker=getattr(c, "speaker", ""),
                        )
                        for c in enhanced_clips
                    ]
                except Exception as tts_err:
                    logger.warning(
                        "%s TTS failed, falling back to edge-tts: %s",
                        tts_provider, tts_err,
                    )
                    narrations = self._run_stage_with_retry(
                        "narrate",
                        lambda: self.narration_engine.generate_narration(
                            narration_key_points, output_dir,
                        ),
                        tracker,
                    )
            else:
                # Standard single-voice narration (edge-tts)
                # Adapt ScreenSegments → KeyPoint objects for NarrationEngine
                narration_key_points = [
                    KeyPoint(
                        index=screen.index,
                        headline=screen.text[:60],
                        narration=screen.text,
                        visual_query=screen.image_prompt or screen.text[:40],
                        duration=screen.duration,
                        emotion=screen.emotion,
                    )
                    for screen in screenplay.screens
                    if not screen.is_intro and not screen.is_outro
                ]

                narrations = self._run_stage_with_retry(
                    "narrate",
                    lambda: self.narration_engine.generate_narration(
                        narration_key_points, output_dir,
                    ),
                    tracker,
                )

            # ── Post-narration: Silence gaps between clips ──
            if is_enhanced and getattr(config, "ENHANCED_SILENCE_GAPS", False):
                silence_ms = getattr(config, "SCENE_SILENCE_MS", 300)
                padded_count = 0
                for n in narrations:
                    ap = getattr(n, "audio_path", None)
                    if ap and Path(ap).exists():
                        new_dur = append_silence_to_audio(ap, silence_ms=silence_ms)
                        if new_dur is not None and new_dur > n.duration:
                            n.duration = new_dur
                            padded_count += 1
                if padded_count:
                    logger.info(
                        "Added %dms silence gap to %d narration clips",
                        silence_ms, padded_count,
                    )

            total_narration = sum(n.duration for n in narrations)
            logger.info(
                "Narration generated: %.1fs total, %d clips",
                total_narration, len(narrations),
            )
            tracker.complete_stage(
                "narrate",
                f"{total_narration:.1f}s narration generated",
            )

            # ── Duration Check (informational — never drops story content) ──
            # Duration is a SOFT guideline. Story completeness always wins.
            # We only log here; we never remove screens or narration clips.
            min_dur, max_dur = config.TARGET_DURATION
            if target_duration and target_duration > 0:
                overshoot = total_narration - target_duration
                if overshoot > 0:
                    logger.info(
                        "Post-narration: %.1fs total (target: %ds, +%.1fs over — "
                        "acceptable for story completeness)",
                        total_narration, target_duration, overshoot,
                    )
                else:
                    logger.info(
                        "Post-narration: %.1fs total (target: %ds ✓)",
                        total_narration, target_duration,
                    )
            elif total_narration > max_dur:
                logger.info(
                    "Post-narration: %.1fs total (default range %d-%ds — "
                    "over target but preserving full story)",
                    total_narration, min_dur, max_dur,
                )

            # ── Stage 4.5: VFX PLANNING (Claude Opus 4.6) ──
            tracker.start_stage("vfx_plan", "AI VFX Agent planning effects...")
            try:
                effects_plan = generate_effects_plan(
                    screens=screenplay.screens,
                    mood=screenplay.mood,
                    content_mode=content_mode,
                    visual_style=visual_style,
                    use_ai=True,
                )
                logger.info(
                    "VFX plan generated: %d scene plans, theme=%s",
                    len(effects_plan.scenes),
                    effects_plan.visual_theme,
                )
                for sp in effects_plan.scenes:
                    logger.info(
                        "  [%d] entry=%s exit=%s transition=%s overlay=%s | %s",
                        sp.screen_index, sp.text_entry, sp.text_exit,
                        sp.scene_transition, sp.overlay_effect,
                        sp.reasoning[:60] if sp.reasoning else "",
                    )
            except Exception as e:
                logger.warning("VFX planning failed, using defaults: %s", e)
                effects_plan = None
            tracker.complete_stage(
                "vfx_plan",
                f"Effects planned for {len(effects_plan.scenes) if effects_plan else 0} scenes",
            )

            # ── Stage 5: COMPOSE ───────────────────────────
            video_filename = f"{slugify(screenplay.title)}.mp4"

            # Determine enhanced rendering params
            layout_mode = "classic"
            scene_silence_ms = 0
            if is_enhanced:
                if getattr(config, "ENHANCED_FULL_BLEED", False):
                    layout_mode = "fullbleed"
                if getattr(config, "ENHANCED_SILENCE_GAPS", False):
                    scene_silence_ms = getattr(config, "SCENE_SILENCE_MS", 300)

            if renderer == "remotion":
                tracker.start_stage("compose", "Rendering with Remotion React Engine...")
                remotion = RemotionRenderer(
                    video_format=video_format,
                    platform=kwargs.get("platform", ""),
                    visual_style=visual_style,
                )
                try:
                    compose_result = self._run_stage_with_retry(
                        "compose",
                        lambda: remotion.render(
                            screenplay=screenplay,
                            images=images,
                            narrations=narrations,
                            output_dir=output_dir,
                            output_filename=video_filename,
                            effects_plan=effects_plan,
                            include_subtitles=include_subtitles,
                            color_grade=color_grade,
                            brand_text=brand_text,
                            layout_mode=layout_mode,
                            scene_silence_ms=scene_silence_ms,
                            autopilot_hook=kwargs.get("autopilot_hook", ""),
                        ),
                        tracker,
                        max_retries=1,
                    )
                except Exception as remotion_err:
                    if kwargs.get("autopilot_hook"):
                        raise  # Autopilot requires the designed Remotion cover; fail closed.
                    logger.warning("Remotion render failed (%s); seamlessly falling back to ClayCompositor", remotion_err)
                    tracker.start_stage("compose", "Composing video (high-speed fallback)...")
                    compositor = ClayCompositor(
                        video_format=video_format,
                        platform=kwargs.get("platform", ""),
                        visual_style=visual_style,
                    )
                    compose_result = compositor.compose(
                        screenplay=screenplay,
                        images=images,
                        narrations=narrations,
                        output_dir=output_dir,
                        output_filename=video_filename,
                        include_subtitles=include_subtitles,
                        color_grade=color_grade,
                        brand_text=brand_text,
                        effects_plan=effects_plan,
                    )
            else:
                tracker.start_stage("compose", "Composing Claymorphism video...")
                compositor = ClayCompositor(
                    video_format=video_format,
                    platform=kwargs.get("platform", ""),
                    visual_style=visual_style,
                )
                compose_result = self._run_stage_with_retry(
                    "compose",
                    lambda: compositor.compose(
                        screenplay=screenplay,
                        images=images,
                        narrations=narrations,
                        output_dir=output_dir,
                        output_filename=video_filename,
                        include_subtitles=include_subtitles,
                        color_grade=color_grade,
                        brand_text=brand_text,
                        effects_plan=effects_plan,
                    ),
                    tracker,
                    max_retries=1,
                )

            # ── Build Result ───────────────────────────────
            elapsed = time.time() - start_time
            (output_dir / 'opening-assets.json').write_text(json.dumps([
                {'path':str(Path(image.local_path).resolve()),'subject':getattr(image,'query','') or getattr(image,'prompt',''),'role':'object'}
                for image in images if Path(image.local_path).is_file()],default=str))
            result.success = True
            result.video_path = compose_result["video_path"]
            result.srt_path = compose_result.get("srt_path")
            result.thumbnail_path = compose_result.get("thumbnail_path")
            result.duration = compose_result["duration"]
            result.resolution = compose_result["resolution"]
            result.video_format = video_format
            result.title = screenplay.title
            result.key_point_count = len(screenplay.screens)
            result.processing_time = elapsed
            result.hook = screenplay.hook
            result.content_type = content_mode if content_mode != "article" else "ai_claymorphism"
            result.mood = screenplay.mood
            result.theme = visual_style or "claymorphism"
            result.caption_style = "karaoke"

            tracker.complete_stage(
                "compose",
                f"Video rendered ({result.duration:.1f}s)",
            )

            # ── Save series context ────────────────────────
            if series_id and screenplay.cliffhanger:
                self._save_series_context(series_id, {
                    "last_episode": episode_number or 1,
                    "next_episode": (episode_number or 1) + 1,
                    "last_cliffhanger": screenplay.cliffhanger,
                    "last_title": screenplay.title,
                    "content_mode": content_mode,
                })

            logger.info("=" * 60)
            logger.info("AI IMAGE PIPELINE COMPLETE (%s mode)", content_mode)
            logger.info("  Video: %s", result.video_path)
            logger.info("  Duration: %.1fs", result.duration)
            logger.info("  Resolution: %s", result.resolution)
            logger.info("  Screens: %d | AI images: %d", len(screenplay.screens), len(images))
            if series_id:
                logger.info("  Series: %s, Episode: %d", series_id, episode_number or 1)
            logger.info("  Processing time: %.1fs", elapsed)
            logger.info("=" * 60)

            # Save metadata manifest
            self._save_manifest(result, output_dir, {
                "input_source": input_source[:200],
                "tone": tone,
                "video_format": video_format,
                "theme": visual_style or "claymorphism",
                "pipeline": "ai_image",
                "content_mode": content_mode,
                "transition": transition,
                "color_grade": color_grade,
                "voice": self.narration_engine.voice,
                "include_subtitles": include_subtitles,
                "brand_text": brand_text,
                "screen_count": len(screenplay.screens),
                "ai_images_generated": len(images),
                "question": question,
                "character_name": character_name,
                "modern_topic": modern_topic,
                "series_id": series_id,
                "episode_number": episode_number,
                "cliffhanger": screenplay.cliffhanger,
                "screens": [
                    {
                        "index": s.index,
                        "visual_type": s.visual_type,
                        "text": s.text[:80],
                        "emotion": s.emotion,
                        "speaker": s.speaker,
                    }
                    for s in screenplay.screens
                ],
            })

        except Exception as e:
            elapsed = time.time() - start_time
            result.processing_time = elapsed
            result.errors.append(str(e))
            logger.error(
                "AI image pipeline failed after %.1fs: %s",
                elapsed, e, exc_info=True,
            )
            for stage in tracker.stages.values():
                if stage.status == "running":
                    tracker.fail_stage(stage.name, str(e))

        # Restore original config in case it was overridden
        config.TARGET_DURATION = original_target_duration

        return result

    def preview_analysis(
        self,
        input_source: str,
        tone: str = "informative",
        num_points: Optional[int] = None,
    ) -> AnalysisResult:
        """Run only scrape + analyze stages for preview."""
        article = self.scraper.scrape(input_source)
        analysis = self.analyzer.analyze(article, tone=tone, num_points=num_points)
        return analysis

    # ── Duration Enforcement ──────────────────────────────

    def _enforce_duration(
        self,
        article: ArticleData,
        tone: str,
        video_format: str,
        output_dir: Path,
        current_points: int,
        current_duration: float,
        analysis: AnalysisResult,
        theme: str = "cinematic",
    ):
        """
        Re-run analyze → visuals → narrate with adjusted key point count
        if total duration is outside TARGET_DURATION range.
        Returns (analysis, narrations, images) or None if no adjustment possible.
        """
        min_dur, max_dur = config.TARGET_DURATION

        if current_duration > max_dur and current_points > config.MIN_KEY_POINTS:
            new_points = max(config.MIN_KEY_POINTS, current_points - 1)
            logger.info(
                "Duration too long (%.1fs > %ds). Reducing to %d key points.",
                current_duration, max_dur, new_points,
            )
        elif current_duration < min_dur and current_points < config.MAX_KEY_POINTS:
            new_points = min(config.MAX_KEY_POINTS, current_points + 1)
            logger.info(
                "Duration too short (%.1fs < %ds). Increasing to %d key points.",
                current_duration, min_dur, new_points,
            )
        else:
            logger.info(
                "Duration %.1fs outside range (%d-%ds) but cannot adjust points further.",
                current_duration, min_dur, max_dur,
            )
            return None

        try:
            new_analysis = self.analyzer.analyze(
                article, tone=tone, num_points=new_points
            )
            logger.info(
                "Re-analysis done: %d key points", len(new_analysis.key_points)
            )

            # Preserve hook and metadata from original if new is empty
            if not new_analysis.hook and analysis.hook:
                new_analysis.hook = analysis.hook
            if not new_analysis.mood or new_analysis.mood == "neutral":
                new_analysis.mood = analysis.mood

            new_images = self.visual_finder.find_images(
                new_analysis.key_points, output_dir, video_format,
                theme=theme,
            )

            new_narrations = self.narration_engine.generate_narration(
                new_analysis.key_points, output_dir
            )

            new_total = sum(n.duration for n in new_narrations)
            logger.info("Adjusted narration duration: %.1fs", new_total)

            return new_analysis, new_narrations, new_images

        except Exception as e:
            logger.warning("Duration adjustment failed, keeping original: %s", e)
            return None

    # ── Stage-Level Error Recovery ────────────────────────

    def _run_stage_with_retry(
        self,
        stage_name: str,
        func,
        tracker: ProgressTracker,
        max_retries: int = 2,
    ):
        """
        Run a pipeline stage function with retry logic.
        
        Args:
            stage_name: Name for logging.
            func: Callable to execute.
            tracker: Progress tracker for status updates.
            max_retries: Number of retry attempts (0 = no retries, just run once).
            
        Returns:
            The result of the function call.
            
        Raises:
            The last exception if all retries fail.
        """
        last_error = None
        attempts = max_retries + 1  # total attempts = retries + 1

        for attempt in range(attempts):
            try:
                if attempt > 0:
                    wait = config.RETRY_BACKOFF ** attempt
                    logger.info(
                        "Retrying stage '%s' (attempt %d/%d) in %.1fs...",
                        stage_name, attempt + 1, attempts, wait,
                    )
                    tracker.update_stage(
                        stage_name,
                        detail=f"Retry {attempt}/{max_retries}...",
                    )
                    time.sleep(wait)

                result = func()
                return result

            except Exception as e:
                last_error = e
                logger.warning(
                    "Stage '%s' failed (attempt %d/%d): %s",
                    stage_name, attempt + 1, attempts, e,
                )

        # All retries exhausted
        tracker.fail_stage(stage_name, str(last_error))
        raise last_error

    # ── Caching Helpers ───────────────────────────────────

    @staticmethod
    def _analysis_to_dict(analysis: AnalysisResult) -> dict:
        """Serialize AnalysisResult for caching."""
        return {
            "title": analysis.title,
            "tone": analysis.tone,
            "summary": analysis.summary,
            "source_url": analysis.source_url,
            "hook": analysis.hook,
            "content_type": analysis.content_type,
            "mood": analysis.mood,
            "cta": analysis.cta,
            "key_points": [
                {
                    "index": kp.index,
                    "headline": kp.headline,
                    "narration": kp.narration,
                    "visual_query": kp.visual_query,
                    "duration": kp.duration,
                    "emotion": kp.emotion,
                }
                for kp in analysis.key_points
            ],
        }

    @staticmethod
    def _dict_to_analysis(data: dict) -> AnalysisResult:
        """Deserialize AnalysisResult from cache."""
        from agent.analyzer import KeyPoint

        key_points = [
            KeyPoint(
                index=kp["index"],
                headline=kp["headline"],
                narration=kp["narration"],
                visual_query=kp["visual_query"],
                duration=kp.get("duration", 0.0),
                emotion=kp.get("emotion", ""),
            )
            for kp in data.get("key_points", [])
        ]

        return AnalysisResult(
            title=data["title"],
            key_points=key_points,
            tone=data.get("tone", "informative"),
            summary=data.get("summary", ""),
            source_url=data.get("source_url"),
            hook=data.get("hook", ""),
            content_type=data.get("content_type", "general"),
            mood=data.get("mood", "neutral"),
            cta=data.get("cta", ""),
        )

    # ── Series Context Management ────────────────────────

    @staticmethod
    def _load_series_context(series_id: str) -> Optional[dict]:
        """Load series context from JSON file on disk."""
        series_dir = config.SERIES_DIR
        series_file = series_dir / f"{series_id}.json"
        if series_file.exists():
            try:
                data = json.loads(series_file.read_text(encoding="utf-8"))
                logger.info("Loaded series context for '%s': ep %d", series_id, data.get("last_episode", 0))
                return data
            except Exception as e:
                logger.warning("Failed to load series context '%s': %s", series_id, e)
        return None

    @staticmethod
    def _save_series_context(series_id: str, context: dict):
        """Save series context to JSON file on disk."""
        series_dir = config.SERIES_DIR
        series_dir.mkdir(parents=True, exist_ok=True)
        series_file = series_dir / f"{series_id}.json"
        try:
            # Merge with existing data if present
            existing = {}
            if series_file.exists():
                existing = json.loads(series_file.read_text(encoding="utf-8"))
            existing.update(context)
            existing["series_id"] = series_id
            existing["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Track episode history
            episodes = existing.get("episodes", [])
            episodes.append({
                "episode": context.get("last_episode", 1),
                "title": context.get("last_title", ""),
                "cliffhanger": context.get("last_cliffhanger", ""),
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            existing["episodes"] = episodes[-config.SERIES_MAX_EPISODES:]
            
            series_file.write_text(
                json.dumps(existing, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info("Saved series context for '%s' (ep %d)", series_id, context.get("last_episode", 1))
        except Exception as e:
            logger.warning("Failed to save series context '%s': %s", series_id, e)

    # ── Metadata Manifest ─────────────────────────────────

    @staticmethod
    def _save_manifest(
        result: PipelineResult,
        output_dir: Path,
        run_config: dict,
    ):
        """Save a JSON metadata manifest alongside the video output."""
        manifest = {
            "project_her_version": "2.0",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "title": result.title,
            "hook": result.hook,
            "content_type": result.content_type,
            "mood": result.mood,
            "duration_seconds": round(result.duration, 1),
            "resolution": result.resolution,
            "video_format": result.video_format,
            "key_point_count": result.key_point_count,
            "processing_time_seconds": round(result.processing_time, 1),
            "theme": result.theme,
            "caption_style": result.caption_style,
            "video_file": Path(result.video_path).name if result.video_path else None,
            "srt_file": Path(result.srt_path).name if result.srt_path else None,
            "thumbnail_file": Path(result.thumbnail_path).name if result.thumbnail_path else None,
            "config": run_config,
        }

        manifest_path = output_dir / "manifest.json"
        try:
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info("Manifest saved: %s", manifest_path)
        except Exception as e:
            logger.warning("Failed to save manifest: %s", e)
