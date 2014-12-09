#!/usr/bin/env python

import os
import yaml
import re


class ChannelFilter(object):
    def __init__(self, path=None):
        if path is None:
            path = os.path.join(os.path.dirname(__file__), 'channels.yaml')
        with open(path) as f:
            self.config = yaml.load(f)

        self.parse_regexps()
        print(self.config)

    def parse_regexps(self):
        chan_proj_map = self.config['channels']
        for channel in chan_proj_map:
            fullregex = "^(" + "|".join(chan_proj_map[channel]) + ")$"
            chan_proj_map[channel] = re.compile(fullregex, flags=(re.IGNORECASE | re.UNICODE))

    @property
    def firehose_channel(self):
        return self.config['firehose-channel']

    @property
    def default_channel(self):
        return self.config['default-channel']

    def all_channels(self):
        channels = [self.default_channel, self.firehose_channel] + list(self.config['channels'])
        return list(set(channels))

    def channels_for(self, projects):
        """
        :param project: Get all channels to spam for given projects
        :type project: list
        """
        channels = set()
        for channel in self.config['channels']:
            for project in projects:
                if self.config['channels'][channel].match(project):
                    channels.add(channel)
                    break
        if not channels:
            channels.add(self.default_channel)
        channels.add(self.firehose_channel)
        return channels
