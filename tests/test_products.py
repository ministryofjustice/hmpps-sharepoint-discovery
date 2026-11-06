import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from processes import products


class ProductSlackTests(unittest.TestCase):
  def test_resolution(self):
    cases = [
      (' C0123456789\t', 'team-alerts', 'team-alerts|C0123456789', 'C0123456789'),
      ('#team-alerts', 'C0123456789', 'team-alerts|C0123456789', '#team-alerts'),
      ('team-alerts', 'C0123456789', 'team-alerts|C0123456789', 'team-alerts'),
      ('C0123456789', None, 'none|C0123456789', 'C0123456789'),
      ('missing', None, 'missing|none', 'missing'),
    ]
    for channel, counterpart, expected, lookup in cases:
      with self.subTest(channel=channel):
        slack = Mock()
        slack.get_slack_channel_counterpart.return_value = counterpart
        self.assertEqual(products.resolve_slack_channel(slack, channel), expected)
        slack.get_slack_channel_counterpart.assert_called_once_with(lookup)

  def test_empty_values_do_not_call_slack(self):
    for channel in (None, '', ' \t'):
      with self.subTest(channel=channel):
        slack = Mock()
        self.assertEqual(products.resolve_slack_channel(slack, channel), '')
        slack.get_slack_channel_counterpart.assert_not_called()

  def process(self, source, existing, counterpart='team-alerts'):
    sc = Mock()
    sc.sharepoint_discovery_products_get = 'products'
    sc.get_all_records.side_effect = [existing, [], [], []]
    slack = Mock()
    slack.get_slack_channel_counterpart.return_value = counterpart
    services = SimpleNamespace(sc=sc, slack=slack, sp=Mock())
    with patch.object(products, 'extract_sp_products_data', return_value=[source]):
      products.process_sc_products(services)
    return sc, slack

  def test_existing_product_updates_only_changed_slack_field(self):
    sc, _ = self.process(
      {'p_id': 'DPS001', 'name': 'Product', 'slack_channel_id': ' C0123456789\t'},
      [{
        'p_id': 'DPS001', 'name': 'Product', 'documentId': 'doc',
        'slack_channel_id': 'C0123456789', 'slack_channel_name': 'legacy',
      }],
    )
    sc.update.assert_called_once_with(
      'products', 'doc',
      {'p_id': 'DPS001', 'slack_channel_id': 'team-alerts|C0123456789'},
    )
    sc.add.assert_not_called()

  def test_unchanged_channel_does_not_update(self):
    sc, _ = self.process(
      {'p_id': 'DPS001', 'slack_channel_id': 'C0123456789'},
      [{
        'p_id': 'DPS001', 'name': 'Product', 'documentId': 'doc',
        'slack_channel_id': 'team-alerts|C0123456789',
      }],
    )
    sc.update.assert_not_called()

  def test_renamed_channel_updates(self):
    sc, _ = self.process(
      {'p_id': 'DPS001', 'slack_channel_id': 'C0123456789'},
      [{
        'p_id': 'DPS001', 'name': 'Product', 'documentId': 'doc',
        'slack_channel_id': 'old-name|C0123456789',
      }],
    )
    self.assertEqual(
      sc.update.call_args.args[2]['slack_channel_id'], 'team-alerts|C0123456789'
    )

  def test_missing_catalogue_field_is_populated(self):
    sc, _ = self.process(
      {'p_id': 'DPS001', 'slack_channel_id': 'C0123456789'},
      [{'p_id': 'DPS001', 'name': 'Product', 'documentId': 'doc'}],
    )
    sc.update.assert_called_once()

  def test_empty_source_clears_stale_channel(self):
    sc, slack = self.process(
      {'p_id': 'DPS001', 'slack_channel_id': None},
      [{
        'p_id': 'DPS001', 'name': 'Product', 'documentId': 'doc',
        'slack_channel_id': 'old-name|C0123456789',
      }],
    )
    self.assertEqual(sc.update.call_args.args[2]['slack_channel_id'], '')
    slack.get_slack_channel_counterpart.assert_not_called()

  def test_new_product_includes_resolved_channel(self):
    sc, _ = self.process(
      {'p_id': 'DPS001', 'name': 'Product', 'slack_channel_id': 'C0123456789'}, []
    )
    sc.add.assert_called_once_with(
      'products',
      {
        'p_id': 'DPS001', 'name': 'Product',
        'slack_channel_id': 'team-alerts|C0123456789',
      },
    )
    sc.update.assert_not_called()
