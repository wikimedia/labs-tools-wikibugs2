import wikibugs
import configfetcher
import unittest
import os

p = os.path.split(__file__)[0]


class TestWikibugs(unittest.TestCase):
    def setUp(self):
        self.bugs = wikibugs.Wikibugs2(
            configfetcher.ConfigFetcher()
        )

    def test_offline_scrape(self):
        content = open(p + "/T87834", encoding="utf-8").read()
        tags = self.bugs.get_tags(content)
        self.assertSetEqual(set(tags), {
            '§ Fundraising Sprint Devo',
            '§ Fundraising Tech Backlog',
            'Wikimedia-Fundraising',
            'Wikimedia-Fundraising-CiviCRM',
        })
        self.assertSetEqual(set(next(iter(tags.values()))), {
            'shade',
            'disabled',
            'uri',
            'tagtype'
        })
