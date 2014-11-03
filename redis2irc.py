#!/usr/bin/env python

from irc.bot import ServerSpec, SingleServerIRCBot

import configfetcher
import messagebuilder
import rqueue


class Redis2IRC(SingleServerIRCBot):
    def __init__(self, conf, builder):
        """
        :type conf: configfetcher.ConfigFetcher
        :type builder: messagebuilder.IRCMessageBuilder
        """
        super(Redis2IRC, self).__init__(
            [ServerSpec(conf.get('IRC_SERVER'))],
            conf.get('IRC_NICK'),
            conf.get('IRC_NICK'),
        )
        self.rqueue = rqueue.RedisQueue(
            conf.get('REDIS_QUEUE_NAME'),
            conf.get('REDIS_HOST')
        )
        self.conf = conf
        self.join_channels = conf.get('CHANNELS').values()
        self.builder = builder
        self.connected = False

    def on_welcome(self, c, e):
        print 'welcome!'
        for chan in self.join_channels:
            c.join(chan)
        self.connected = True

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
        for i in ['welcome']:
            self.connection.add_global_handler(i, getattr(self, "on_" + i), -20)
        self._connect()
        #for chan in self.join_channels:
        #    self.manifold.server().join(chan)
        while 1:
            self.manifold.process_once(0.1)
            if self.connected:
                print 'checking redis...'
                useful_info = self.rqueue.get(False)
                if useful_info:
                    text = self.builder.build_message(useful_info)
                    channels = self.get_channels_for_projects(useful_info['projects'])
                    for channel in channels:
                        if not channel in self.channels:
                            print self.channels
                            self.manifold.server().join(channel)
                        self.manifold.server().privmsg(channel, text)

if __name__ == '__main__':
    bot = Redis2IRC(
        configfetcher.ConfigFetcher(),
        messagebuilder.IRCMessageBuilder()
    )
    bot.start()
