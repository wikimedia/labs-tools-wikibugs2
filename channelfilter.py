#!/usr/bin/env python

import os
import yaml


class ChannelFilter(object):
    def __init__(self, path=None):
        if path is None:
            path = os.path.join(os.path.dirname(__file__), 'channels.yaml')
        with open(path) as f:
            self.config = yaml.load(f)

        print(self.config)

    def channels_for(self, project):
        """
        :param project: Get all channels to spam for the given project
        :type project: basestring
        """
        channels = set()
        for channel in self.config['channels']:
            if project in self.config['channels'][channel]:
                channels.add(channel)
                continue
        channels.add(self.config['firehose-channel'])
        print(channels)
        return channels
