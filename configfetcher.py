#!/usr/bin/env python

import json
import os


class ConfigFetcher(object):
    """
    A simple wrapper around a JSON file,
    in the future it might do more fancy things
    maybe!
    """

    filename = 'config.json'

    def __init__(self):
        self.filename = os.path.join(os.path.dirname(__file__), self.filename)
        with open(self.filename) as f:
            self.file_options = json.load(f)

    def get(self, name):
        return self.file_options.get(name)
