#!/usr/bin/env python

import os
import time
import yaml

import configfetcher
import messagebuilder
import rqueue
import channelfilter


class Redis2Stdout(object):
    def __init__(self, conf, builder, channelfilter):
        """
        :type conf: configfetcher.ConfigFetcher
        :type builder: messagebuilder.IRCMessageBuilder
        """
        self.rqueue = rqueue.RedisQueue(
            conf.get('REDIS_QUEUE_NAME'),
            conf.get('REDIS_HOST')
        )
        self.conf = conf
        self.join_channels = conf.get('CHANNELS').values()
        self.builder = builder
        self.connected = False
        self.channelfilter = channelfilter

    def get_channels_for_projects(self, projects):
        """
        :param projects: List of human readable project names
        :type projects: list
        """
        channels = set()
        for proj in projects:
            proj_channels = self.channelfilter.channels_for(proj)
            if proj_channels:
                channels.union(proj_channels)

        return channels

    def start(self):
        while 1:
            time.sleep(0.1)
            useful_info = self.rqueue.get()
            print useful_info
            if useful_info:
                text = self.builder.build_message(useful_info)
                channels = self.get_channels_for_projects(useful_info['projects'])
                print ','.join(channels) + ': ' + text

if __name__ == '__main__':
    channels_path = os.path.join(os.path.dirname(__file__), 'channels.yaml')
    with open(channels_path) as f:
        channel_filter = yaml.load(f)

    bot = Redis2Stdout(
        configfetcher.ConfigFetcher(),
        messagebuilder.IRCMessageBuilder(),
        channelfilter.ChannelFilter(channel_filter)
    )
    bot.start()