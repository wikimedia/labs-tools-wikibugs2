#!/usr/bin/env python

import asyncio
import asyncio_redis
import asyncio_redis.encoders
import irc3
import logging
import logging.config
import traceback

import channelfilter
import configfetcher
import messagebuilder

__version__ = '3.0alpha'


class Redis2Irc(irc3.IrcBot):
    def __init__(self, conf, builder, chanfilter, **kwargs):
        """
        :type conf: configfetcher.ConfigFetcher
        :type builder: messagebuilder.IRCMessageBuilder
        :type chanfilter: channelfilter.ChannelFilter
        """
        super(Redis2Irc, self).__init__(**kwargs)
        self._conf = conf
        self._builder = builder
        self._chanfilter = chanfilter

    @property
    def conf(self):
        return self._conf

    @property
    def builder(self):
        return self._builder

    @property
    def chanfilter(self):
        return self._chanfilter


@asyncio.coroutine
def handle_useful_info(bot, useful_info):
    """
    :type bot: Redis2Irc
    :type useful_info: dict
    """
    text = bot.builder.build_message(useful_info)
    channels = bot.chanfilter.channels_for(useful_info['projects'])
    for chan in channels:
        bot.privmsg(chan, text)


@asyncio.coroutine
def redisrunner(bot):
    """
    :type bot: Redis2Irc
    """
    while True:
        try:
            yield from redislistener(bot)
        except Exception:
            bot.log.critical(traceback.format_exc())
            bot.log.info("...restarting Redis listener in a few seconds.")
        yield from asyncio.sleep(5)


@asyncio.coroutine
def redislistener(bot):
    """
    :type bot: Redis2Irc
    """
    # Create connection
    connection = yield from asyncio_redis.Connection.create(
        host=bot.conf.get('REDIS_HOST'),
        port=6379,
        encoder=asyncio_redis.encoders.BytesEncoder()
    )

    # Create subscriber.
    subscriber = yield from connection.start_subscribe()

    # Subscribe to channel.
    yield from subscriber.subscribe([bytes(bot.conf.get('REDIS_QUEUE_NAME'), 'ascii')])
    # Inside a while loop, wait for incoming events.
    while True:
        try:
            useful_info = yield from subscriber.next_published()
            asyncio.Task(handle_useful_info(bot, useful_info))  # Do not wait for response
        except Exception:
            bot.log.critical(traceback.format_exc())
            yield from asyncio.sleep(1)


def main():
    conf = configfetcher.ConfigFetcher()
    chanfilter = channelfilter.ChannelFilter()
    bot = Redis2Irc(
        conf=conf,
        builder=messagebuilder.IRCMessageBuilder(),
        chanfilter=chanfilter,
        nick=conf.get('IRC_NICK'),
        autojoins=chanfilter.all_channels(),
        host=conf.get('IRC_SERVER'),
        port=7000,
        ssl=True,
        password=conf.get('IRC_PASSWORD'),
        realname='wikibugs2',
        userinfo='Wikibugs v2.1, http://tools.wmflabs.org/wikibugs/',
        includes=[
            'irc3.plugins.core',
            'irc3.plugins.ctcp',
            'irc3.plugins.autojoins',
            __name__,  # this register MyPlugin
        ],
        verbose=True,
        ctcp={
            'version': 'wikibugs2 %s running on irc3 {version}. See {url} for more details.' % __version__,
            'userinfo': '{userinfo}',
            'ping': 'PONG',
        }
    )
    asyncio.Task(redisrunner(bot))
    bot.run()

if __name__ == '__main__':
    main()
