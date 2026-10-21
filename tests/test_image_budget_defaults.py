"""Default event capacity fits the audit; explicit spending caps remain hard."""
import os
import unittest
from unittest.mock import patch
from agent.editorial.image_policy import ImagePolicy
from agent.news_models import NewsError


class ImageBudgetDefaultsTests(unittest.TestCase):
    def test_clean_environment_fits_reported_fifteen_image_ten_action_job(self):
        with patch.dict(os.environ,{},clear=True):
            policy=ImagePolicy.load()
        self.assertEqual(policy.image_budget,.60)
        self.assertEqual(policy.total_budget,.80)
        self.assertGreaterEqual(policy.max_images,15)
        self.assertGreaterEqual(policy.max_actions,10)
        policy.check(0,10*policy.seedream_price+5*policy.schnell_price)

    def test_complete_twelve_event_fixture_fits_defaults_without_overrun(self):
        from scripts.evaluate_sisyphus import sample
        from agent.editorial.asset_planner import finalize
        with patch.dict(os.environ,{},clear=True):
            _,script,_,_=sample()
            plan=finalize(script)
        self.assertEqual(plan['status'],'ready')
        self.assertEqual(plan['seedream_count'],12)
        self.assertAlmostEqual(plan['estimated_image_cost_usd'],.378)
        self.assertEqual(plan['limits']['max_images'],24)
        self.assertEqual(plan['limits']['max_action_images'],16)

    def test_explicit_lower_budget_still_blocks_with_actionable_amounts(self):
        with patch.dict(os.environ,{'MAX_IMAGE_BUDGET_USD':'.12'},clear=True):
            policy=ImagePolicy.load()
        with self.assertRaisesRegex(NewsError,r'\$0\.315 vs image budget \$0\.120'):
            policy.check(0,.315)

    def test_total_budget_includes_service_reservation(self):
        with patch.dict(os.environ,{'MAX_TOTAL_VIDEO_BUDGET_USD':'.35'},clear=True):
            policy=ImagePolicy.load()
        with self.assertRaisesRegex(NewsError,r'total \$0\.395 vs video budget \$0\.350'):
            policy.check(0,.315)

    def test_new_budget_alias_keeps_precedence(self):
        with patch.dict(os.environ,{'IMAGE_ESTIMATED_BUDGET_USD':'.45','MAX_IMAGE_BUDGET_USD':'.12'},clear=True):
            self.assertEqual(ImagePolicy.load().image_budget,.45)

if __name__=='__main__':unittest.main()
