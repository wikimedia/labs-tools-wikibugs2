#!/usr/bin/env python

import json
import requests
import time


class ConfigFetcher(object):

    filename = 'config.json'
    page = 'User:Legoktm/thing.json'

    def __init__(self):
        with open(self.filename) as f:
            self.file_options = json.load(f)
        self._wiki_options = None
        self.last_revid = 0
        self.last_check = 0

    def get(self, name):
        if name in self.file_options:
            return self.file_options[name]
        return self.wiki_options[name]

    @property
    def wiki_options(self):
        if self._wiki_options is None or time.time() > (self.last_check + 300):
            self.fetch_from_wiki()
        return self._wiki_options

    def fetch_from_wiki(self):
        params = {
            'action': 'query',
            'titles': self.page,
            'prop': 'info|revisions',
            'rvprop': 'content',
            'format': 'json',
        }
        r = requests.get('https://www.mediawiki.org/w/api.php', params=params)
        j = r.json()
        self.last_check = time.time()
        info = j['query']['pages'].values()[0]
        if self.last_revid == info['lastrevid']:
            # No changes
            return
        self._wiki_options = json.loads(info['revisions'][0]['*'])
        self.last_revid = info['lastrevid']
