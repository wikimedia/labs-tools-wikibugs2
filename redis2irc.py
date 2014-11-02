#!/usr/bin/env python

from irc.bot import ServerSpec, SingleServerIRCBot

import configfetcher
import rqueue


class Redis2IRC(SingleServerIRCBot):
    def __init__(self, conf):
        """
        :type conf: configfetcher.ConfigFetcher
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
        self.join_channels = conf.get('CHANNELS').values()

    def start(self):
        self._connect()
        #for chan in self.join_channels:
        #    self.manifold.server().join(chan)
        while 1:
            self.manifold.process_once(0.1)
            msg = self.rqueue.get(False)
            if msg:
                channels = msg.get('channels', [])
                text = msg.get('text', '')
                for channel in channels:
                    if not channel in self.channels:
                        self.manifold.server().join(channel)
                    self.manifold.server().privmsg(channel, text)

if __name__ == '__main__':
    bot = Redis2IRC(configfetcher.ConfigFetcher())
    bot.start()
