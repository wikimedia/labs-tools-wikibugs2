#!/usr/bin/env python

import asyncio
import asyncio_redis
import asyncio_redis.encoders
import json
import irc3
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
        self.channels = set(kwargs['autojoins'])
        super(Redis2Irc, self).__init__(**kwargs)
        self._conf = conf
        self._builder = builder
        self._chanfilter = chanfilter

    def join_many(self, targets):
        for target in targets:
            if target not in self.channels:
                self.join(target)

    def join(self, target):
        super(Redis2Irc, self).join(target)
        self.channels.add(target)

    def part(self, target, reason=None):
        super(Redis2Irc, self).part(target, reason)
        if target in self.channels:
            self.channels.remove(target)

    def privmsg(self, target, message):
        if target not in self.channels:
            self.join(target)
        super(Redis2Irc, self).privmsg(target, message)

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
    if useful_info['user'] == 'gerritbot':
        # Ignore "Patch to review" stuff
        return
    text = bot.builder.build_message(useful_info)
    updated = bot.chanfilter.update()
    if updated:
        bot.privmsg('#wikimedia-labs', '!log tools.wikibugs Updated channels.yaml to: %s' % updated)

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
    )

    while True:
        try:
            future = yield from connection.blpop([bot.conf.get('REDIS_QUEUE_NAME')])
            useful_info = json.loads(future.value)
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
        autojoins=['#wikimedia-labs'],
        host=conf.get('IRC_SERVER'),
        port=6667,
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
