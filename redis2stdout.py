#!/usr/bin/env python

import time

import configfetcher
import messagebuilder
import rqueue
import channelfilter

import logging
logging.basicConfig(level=logging.DEBUG)


class Redis2Stdout(object):
    def __init__(self, conf, builder, channelfilter):
        """
        :type conf: configfetcher.ConfigFetcher
        :type builder: messagebuilder.IRCMessageBuilder
        :type channelfilter: channelfilter.ChannelFilter
        """
        self.rqueue = rqueue.RedisQueue(
            conf.get('REDIS_QUEUE_NAME'),
            conf.get('REDIS_HOST')
        )
        self.conf = conf
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
            print(useful_info)
            if useful_info:
                useful_info['matched_projects'] = list(useful_info['projects'])[:]
                useful_info['channel'] = '#wikimedia-labs'
                text = self.builder.build_message(useful_info)
                updated = self.channelfilter.update()
                if updated:
                    print('!log tools.wikibugs Updated channels.yaml to: %s' % updated)

                channels = self.get_channels_for_projects(useful_info['projects'])
                print(','.join(channels) + ': ' + repr(text))

if __name__ == '__main__':
    bot = Redis2Stdout(
        configfetcher.ConfigFetcher(),
        messagebuilder.IRCMessageBuilder(),
        channelfilter.ChannelFilter()
    )
    bot.start()
