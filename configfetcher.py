#!/usr/bin/env python

import json
import os


class ConfigFetcher(object):
    """
    A simple wrapper around a JSON file,
    in the future it might do more fancy things
    maybe!
    """

    def __init__(self, filename=None):
        if not filename:
            filename = os.path.join(os.path.dirname(__file__), "config.json")

        with open(filename) as f:
            self.file_options = json.load(f)

    def get(self, name):
        return self.file_options.get(name)
