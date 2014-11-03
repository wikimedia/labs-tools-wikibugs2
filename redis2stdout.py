#!/usr/bin/env python

import time

import configfetcher
import messagebuilder
import rqueue


class Redis2Stdout(object):
    def __init__(self, conf, builder):
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

    def get_channels_for_projects(self, projects):
        """
        :param projects: List of human readable project names
        :type projects: list
        """
        channels = []
        conf_channels = self.conf.get('CHANNELS')
        for proj in projects:
            if proj in conf_channels:
                channels.append(conf_channels[proj])

        # Send to the default channel if we're not sending it
        # anywhere else
        if not channels and '_default' in conf_channels:
            channels.append(conf_channels['_default'])

        # Don't forget the firehose!
        if '_firehose' in conf_channels:
            channels.append(conf_channels['_firehose'])

        return channels

    def start(self):
        while 1:
            time.sleep(0.1)
            useful_info = self.rqueue.get(False)
            if useful_info:
                text = self.builder.build_message(useful_info)
                channels = self.get_channels_for_projects(useful_info['projects'])
                print ','.join(channels) + ': ' + text

if __name__ == '__main__':
    bot = Redis2Stdout(
        configfetcher.ConfigFetcher(),
        messagebuilder.IRCMessageBuilder()
    )
    bot.start()
