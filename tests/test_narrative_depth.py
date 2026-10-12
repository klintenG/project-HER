"""Unit tests for narrative depth, story pacing, and dynamic visual scaling.

Verifies that Project HER creates comprehensive, engaging narrations with
adaptive screen/point scaling instead of rushing through 20-30 second summaries.
"""

import unittest
from unittest.mock import MagicMock, patch

import config
from agent.analyzer import ContentAnalyzer
from agent.news_models import Claim, Entity, Evidence, Input, Script, Sentence, Source
from agent.news_script import write_script
from agent.scraper import ArticleData
from agent.story_splitter import StorySplitter


class TestConfigNarrativeDepth(unittest.TestCase):
    """Verify configuration constants enforce in-depth narration and visual coverage."""

    def test_key_points_bounds(self):
        self.assertGreaterEqual(config.MIN_KEY_POINTS, 5)
        self.assertGreaterEqual(config.MAX_KEY_POINTS, 12)

    def test_default_target_durations(self):
        self.assertGreaterEqual(config.TARGET_DURATION[0], 60)
        self.assertGreaterEqual(config.TARGET_DURATION[1], 90)
        self.assertGreaterEqual(config.NEWS_DEFAULT_DURATION, 70)
        self.assertGreaterEqual(config.NEWS_MAX_REAL_IMAGE_CALLS, 16)

    def test_platform_presets_durations_and_points(self):
        for name, preset in config.PLATFORM_PRESETS.items():
            self.assertGreaterEqual(
                preset["target_duration"][0],
                30,
                f"Platform preset {name} min duration should be at least 30s",
            )
            self.assertGreaterEqual(
                preset["max_points"],
                6,
                f"Platform preset {name} max points should be at least 6",
            )


class TestContentAnalyzerNarrativeDepth(unittest.TestCase):
    """Verify ContentAnalyzer scales key points and builds deep narrative prompts."""

    @patch("agent.analyzer.get_llm_client")
    def setUp(self, mock_get_llm):
        mock_get_llm.return_value = (MagicMock(), "test-model")
        self.analyzer = ContentAnalyzer()

    def test_adaptive_key_points_by_word_count(self):
        captured_prompts = []

        def fake_call_llm(prompt):
            captured_prompts.append(prompt)
            return {
                "title": "Test Title",
                "key_points": [
                    {
                        "headline": f"Point {i}",
                        "narration": f"Narration {i}",
                        "visual_query": f"Visual {i}",
                        "emotion": "curiosity",
                    }
                    for i in range(8)
                ],
                "summary": "Summary",
                "hook": "Hook",
                "cta": "CTA",
            }

        self.analyzer._call_llm_with_retry = fake_call_llm

        test_cases = [
            (50, 6),     # <100 words -> 6 points
            (250, 7),    # <300 words -> 7 points
            (500, 8),    # <600 words -> 8 points
            (900, 10),   # <1200 words -> 10 points
            (1500, 12),  # >=1200 words -> 12 points
        ]

        for wc, expected_pts in test_cases:
            captured_prompts.clear()
            article = ArticleData(
                title="Test Article",
                text="word " * wc,
                source_url="https://example.com",
            )
            self.analyzer.analyze(article)
            self.assertIn(
                f"Create exactly {expected_pts} key points as a rich, multi-beat DELAYED-REVEAL NARRATIVE ARC",
                captured_prompts[0],
                f"Word count {wc} should request {expected_pts} points",
            )

    def test_topic_prompt_directive_for_short_input(self):
        article_short = ArticleData(
            title="Short Prompt",
            text="Explain the Fermi Paradox and the Great Filter.",
            source_url="",
        )
        prompt = self.analyzer._build_prompt(article_short, "informative", 8)
        self.assertIn("TOPIC PROMPT DIRECTIVE", prompt)
        self.assertIn("Do not summarize in 20-30 seconds", prompt)
        self.assertIn("8-scene narrative script", prompt)

    def test_prompt_rules_enforce_multi_sentence_and_full_duration(self):
        article = ArticleData(
            title="Standard Article",
            text="Lorem ipsum " * 100,
            source_url="",
        )
        prompt = self.analyzer._build_prompt(article, "informative", 8)
        # Should NOT contain 25-35 seconds restriction
        self.assertNotIn("25-35 seconds", prompt)
        # Should enforce 60-90 seconds total pace
        self.assertIn("60-90 seconds", prompt)
        self.assertIn("2-3 SPOKEN sentences", prompt)


class TestStorySplitterNarrativeDepth(unittest.TestCase):
    """Verify StorySplitter pacing instructions and visual scene cutting."""

    def test_default_pacing_block_in_depth_60_to_90s(self):
        pacing = StorySplitter._build_pacing_block(0)
        self.assertIn("60-90 seconds total", pacing)
        self.assertIn("8-16 screens", pacing)
        self.assertIn("NEVER produce a brief, superficial 20-30 second summary", pacing)
        self.assertIn("Every single screen must have a descriptive image prompt", pacing)

    def test_custom_target_duration_pacing_scaling(self):
        # Target 60s
        pacing_60 = StorySplitter._build_pacing_block(60)
        self.assertIn("around 60 seconds", pacing_60)
        self.assertIn("~150 words of narration", pacing_60)
        self.assertIn("8-15 screens", pacing_60)

        # Target 120s
        pacing_120 = StorySplitter._build_pacing_block(120)
        self.assertIn("around 120 seconds", pacing_120)
        self.assertIn("~300 words of narration", pacing_120)
        self.assertIn("17-24 screens", pacing_120)

    @patch("agent.story_splitter.get_llm_client")
    def test_system_prompt_mandates_captivating_beats_and_depth(self, mock_get_llm):
        mock_get_llm.return_value = (MagicMock(), "test-model")
        splitter = StorySplitter()

        article_sys = splitter._system_prompt("article")
        self.assertIn("8-16 screens", article_sys)
        self.assertIn("not a rushed 20-second summary", article_sys)

        kids_sys = splitter._system_prompt("kids_story")
        self.assertIn("50-75 second videos", kids_sys)

    @patch("agent.story_splitter.get_llm_client")
    def test_build_prompt_topic_expansion(self, mock_get_llm):
        mock_get_llm.return_value = (MagicMock(), "test-model")
        splitter = StorySplitter()

        prompt = splitter._build_prompt(
            text="A detective discovers that time flows backwards inside an antique clock shop.",
            title="The Clock Shop",
            tone="storytelling",
            target_duration=0,
        )
        self.assertIn("TOPIC PROMPT DIRECTIVE:", prompt)
        self.assertIn("8-16 screens", prompt)
        self.assertIn("Never create a brief 20-30 second summary", prompt)
        self.assertIn("100% of screens MUST have visual_type \"image\"", prompt)


class TestNewsModelsAndScriptDepth(unittest.TestCase):
    """Verify News model entities limit and multi-beat script generation."""

    def test_script_supports_up_to_24_entities_and_24_sentences(self):
        entities = [
            Entity(
                id=f"e{i}",
                name=f"Entity {i}",
                kind="person",
                description=f"A distinct individual person {i}",
                identity="generic",
            )
            for i in range(24)
        ]
        sentences = [
            Sentence(
                id=f"s{i}",
                text=f"Sentence {i} describing an in-depth story development with rich context.",
                phrase=f"Sentence {i}",
                role="development" if 0 < i < 23 else ("hook" if i == 0 else "close"),
                claim_ids=["c1"],
                entity_ids=[f"e{i}"],
                emphasis=["story"],
            )
            for i in range(24)
        ]

        script = Script(
            summary="A comprehensive news explainer.",
            narration=" ".join(s.text for s in sentences),
            sentences=sentences,
            entities=entities,
        )
        self.assertEqual(len(script.entities), 24)
        self.assertEqual(len(script.sentences), 24)

    def test_write_script_prompt_and_defaults(self):
        calls = []

        def mock_llm_fn(instruction, data):
            calls.append((instruction, data))
            if instruction.startswith("Write"):
                return {
                    "summary": "Deep news summary",
                    "narration": "Hook line. Context line. Development line. Close line.",
                    "sentences": [
                        {
                            "id": "s1",
                            "text": "Hook line.",
                            "phrase": "Hook",
                            "role": "hook",
                            "claim_ids": ["c1"],
                            "entity_ids": ["jwst"],
                            "emphasis": ["Hook"],
                        },
                        {
                            "id": "s2",
                            "text": "Context line.",
                            "phrase": "Context",
                            "role": "context",
                            "claim_ids": ["c1"],
                            "entity_ids": ["jwst"],
                            "emphasis": ["Context"],
                        },
                        {
                            "id": "s3",
                            "text": "Development line.",
                            "phrase": "Development",
                            "role": "development",
                            "claim_ids": ["c1"],
                            "entity_ids": ["jwst"],
                            "emphasis": ["Development"],
                        },
                        {
                            "id": "s4",
                            "text": "Close line.",
                            "phrase": "Close",
                            "role": "close",
                            "claim_ids": ["c1"],
                            "entity_ids": ["jwst"],
                            "emphasis": ["Close"],
                        },
                    ],
                    "entities": [
                        {
                            "id": "jwst",
                            "name": "JWST",
                            "kind": "object",
                            "description": "Space telescope observatory",
                            "identity": "real",
                            "reference_query": "James Webb Space Telescope",
                            "exact_asset": None,
                        }
                    ],
                }
            if instruction.startswith("Check"):
                return {"supported": True, "problems": []}
            return {}

        input_res = Input(
            original="James Webb Space Telescope discoveries 2026",
            normalized="james webb space telescope discoveries 2026",
            subject="James Webb Space Telescope",
            event_date="2026",
            entities=["JWST"],
            places=[],
            kind="topic_query",
            basis="reported",
            assumptions=[],
        )
        src = Source(
            id="src1",
            url="https://nasa.gov",
            title="NASA Space News",
            retrieved_at="2026-10-12T00:00:00Z",
            text="JWST spotted new galaxy in deep space.",
        )
        claim = Claim(
            id="c1",
            source_ids=["src1"],
            text="JWST spotted new galaxy",
            excerpts={"src1": "JWST spotted new galaxy"},
        )
        evidence = Evidence(
            sources=[src],
            claims=[claim],
            conflicts=[],
            unresolved=[],
            verification="single_source",
        )

        script = write_script(input_res, evidence, mock_llm_fn)
        self.assertIsNotNone(script)

        # Inspect LLM write invocation
        write_instruction, write_payload = calls[0]
        self.assertIn("8 to 16 spoken sentences/beats", write_instruction)
        self.assertEqual(write_payload.get("target_seconds"), 75)
        self.assertEqual(write_payload.get("word_budget"), round(75 * 2.4))
        self.assertIn("8-16 sentences with rich narrative depth", write_payload.get("target_sentences", ""))


if __name__ == "__main__":
    unittest.main()

