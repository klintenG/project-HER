"""Cost reporting and the single-output action-model contract."""
import unittest
import config
from utils.cost_tracking import summarize_model_usage_and_costs


class ImageCostTests(unittest.TestCase):
    def test_schnell_seedream_costs_and_retries_are_separate_from_rejection_cost(self):
        records=[
            dict(model_name=config.SIMPLE_IMAGE_MODEL,prediction_id='s1',estimated_cost=.003,status='succeeded',outcome='rejected',tier='person',retry_number=1),
            dict(model_name=config.SIMPLE_IMAGE_MODEL,prediction_id='s2',estimated_cost=.003,status='succeeded',outcome='accepted',tier='person',retry_number=2),
            dict(model_name=config.ACTION_IMAGE_MODEL,prediction_id='a1',estimated_cost=.030,status='succeeded',outcome='accepted',tier='action',retry_number=1),
            dict(model_name=config.ACTION_IMAGE_MODEL,prediction_id=None,estimated_cost=.030,status='http_429')]
        report=summarize_model_usage_and_costs(records)
        self.assertEqual(report['flux_schnell']['count'],2)
        self.assertEqual(report['seedream_4']['count'],1)
        self.assertAlmostEqual(report['total_estimated_replicate_cost'],.036)
        self.assertAlmostEqual(report['role_breakdown']['retries'],.003)
        self.assertAlmostEqual(report['cost_of_rejected_images'],.003)
        self.assertIsNone(report['actual_billed_cost'])
        self.assertIn('Seedream 4: 1 images',report['formatted_text'])
        self.assertEqual(set(report['model_counts']),{config.SIMPLE_IMAGE_MODEL,config.ACTION_IMAGE_MODEL})

    def test_unpriced_archived_record_is_disclosed_without_guessing_a_model_price(self):
        report=summarize_model_usage_and_costs([dict(model_name='archived/unknown-model',prediction_id='old')])
        self.assertEqual(report['unpriced_prediction_count'],1)
        self.assertIn('Unpriced Predictions: 1',report['formatted_text'])


if __name__=='__main__':unittest.main()
