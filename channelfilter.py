#!/usr/bin/env python

import os
import subprocess
import time
import yaml
import re


class ChannelFilter(object):
    def __init__(self, path=None):
        if path is None:
            path = os.path.join(os.path.dirname(__file__), 'channels.yaml')
        self.path = path
        self.time = 0
        self.mtime = 0
        self.config = {}
        self.load()

    def load(self):
        with open(self.path, encoding='utf-8') as f:
            self.config = yaml.load(f)

        self.parse_regexps()
        self.time = time.time()
        self.mtime = os.path.getmtime(self.path)
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
        return [c for c in set(channels) if c.startswith('#')]

    def update(self):
        if time.time() - self.time > 60:
            mtime = os.path.getmtime(self.path)
            if mtime != self.mtime:
                self.load()
                cwd = os.getcwd()
                os.chdir(os.path.dirname(self.path))
                desc = subprocess.check_output(['git', 'rev-list', 'HEAD', '--max-count=1', '--pretty=oneline'])
                os.chdir(cwd)
                return desc.decode().strip()
        return False

    def channels_for(self, projects):
        """
        :param project: Get all channels to spam for given projects
        :type project: iterable
        """
        channels = set()
        for channel in self.config['channels']:
            for project in projects:
                if self.config['channels'][channel].match(project):
                    channels.add(channel)
                    break
        if not channels:
            channels.add(self.default_channel)
        if '/dev/null' in channels:
            channels.remove('/dev/null')
        channels.add(self.firehose_channel)
        return channels
