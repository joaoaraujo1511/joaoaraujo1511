from datetime import date, timedelta
from pathlib import Path
import copy
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import update_activity as activity


def fixture():
    return {'totals': dict(zip(activity.FIELDS, (930, 125, 6))),
            'monthly': {'2025-09': 19, '2025-10': 138, '2025-11': 17, '2025-12': 3,
                        '2026-01': 0, '2026-02': 5, '2026-03': 9, '2026-04': 3,
                        '2026-05': 88, '2026-06': 102, '2026-07': 92,
                        '2026-08': 243, '2026-09': 216, '2026-10': 24},
            'languages': {'Elixir': 2200248, 'JavaScript': 131457, 'HTML': 121977,
                          'CSS': 17368, 'Dockerfile': 7450, 'Shell': 1092},
            'colors': dict(zip(('Elixir','JavaScript','HTML','CSS','Dockerfile','Shell'),
                              ('#8847B9','#f1e05a','#e34c26','#663399','#384d54','#89e051'))),
            'projects': 2, 'date': '2026-10-13', 'updated': '2026-10-13'}


class ActivityTests(unittest.TestCase):
    def test_date_continuity_and_zero_months(self):
        end = date(2026, 3, 1)
        days = {(activity.START + timedelta(days=i)).isoformat(): 0
                for i in range((end-activity.START).days+1)}
        days['2025-09-01'] = 9
        totals = activity.aggregate_daily(days, end)
        self.assertEqual(totals['2025-09'], 9)
        self.assertEqual(totals['2026-02'], 0)
        del days['2026-02-01']
        with self.assertRaises(ValueError): activity.aggregate_daily(days, end)

    def test_safe_svg_and_unlimited_history(self):
        data = fixture()
        data['monthly'] = dict.fromkeys(activity.months_between(activity.START, date(2029, 2, 1)), 0)
        data['languages'] = {'A & <B>': 1}
        data['colors'] = {'A & <B>': '#ffffff'}
        data['date'] = '2029-02-01'
        for theme in ('light', 'dark'):
            root = ET.fromstring(activity.render(data, theme))
            self.assertGreater(int(root.attrib['height']), 800)
            self.assertIn('2025', ''.join(root.itertext()))

    def test_publication_is_idempotent_and_scoped(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'assets').mkdir()
            (root/'assets'/'unrelated.svg').write_text('keep')
            (root/'README.md').write_text('Intro\n## Activity\nold\n### Reach me\nContact')
            data = fixture()
            activity.publish(data, root)
            original = (root/'README.md').read_text()
            activity.publish(data, root)
            self.assertEqual(original, (root/'README.md').read_text())
            data['monthly']['2026-10'] += 1
            activity.publish(data, root)
            self.assertEqual(len(list((root/'assets').glob('activity-auto-*.svg'))), 2)
            self.assertEqual((root/'assets'/'unrelated.svg').read_text(), 'keep')
            self.assertTrue((root/'README.md').read_text().endswith('### Reach me\nContact'))

    def test_reject_missing_token_before_network(self):
        with patch.dict('os.environ', {}, clear=True), patch('urllib.request.urlopen') as network:
            with self.assertRaises(ValueError): activity.request('query { viewer { login } }')
            network.assert_not_called()


if __name__ == '__main__': unittest.main()
