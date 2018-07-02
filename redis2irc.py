#!/usr/bin/env python

import asyncio
import asyncio_redis
import asyncio_redis.encoders
import json
import irc3
import logging
import socket

import channelfilter
import configfetcher
import messagebuilder
from wblogging import LoggingSetupParser

__version__ = '3.0alpha'
current_host = socket.getfqdn()

parser = LoggingSetupParser(
    description="Read bugs from redis, format them and send them to irc",
)
args = parser.parse_args()

logger = logging.getLogger('wikibugs.wb2-irc')


class Redis2Irc(irc3.IrcBot):
    logging_config = {'version': 1}

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

    def privmsg_many(self, targets, message):
        for target in targets:
            self.privmsg(target, message)

    def privmsg(self, target, message):
        # if target not in self.channels:
        #     self.join(target)
        self.join(target)  # FIXME HACK
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
    ignored = ('gerritbot', 'ReleaseTaggerBot', 'Stashbot', 'Phabricator_maintenance', 'CommunityTechBot')
    if useful_info['user'] in ignored:
        # Ignore some Phabricator bots
        logger.debug("Skipped %(url)s by %(user)s" % useful_info)
        return
    updated = bot.chanfilter.update()
    if updated:
        bot.privmsg(
            '#wikimedia-cloud',  # T166420
            '!log tools.wikibugs Updated channels.yaml to: %s' % updated)
        logger.info('Updated channels.yaml to: %s' % updated)

    channels = bot.chanfilter.channels_for(useful_info['projects'])
    for chan, matched_projects in channels.items():
        useful_info['channel'] = chan
        useful_info['matched_projects'] = matched_projects
        text = bot.builder.build_message(useful_info)
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
            logger.exception("Redis listener crashed; restarting in a few seconds.")
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
            if useful_info.get('raw'):
                # grrrrit messages.
                asyncio.Task(bot.privmsg_many(useful_info['channels'], useful_info['msg']))
            else:
                asyncio.Task(handle_useful_info(bot, useful_info))  # Do not wait for response
        except Exception:
            logger.exception("Redis configuration failed; retrying.")


def main():
    conf = configfetcher.ConfigFetcher()
    chanfilter = channelfilter.ChannelFilter()
    bot = Redis2Irc(
        conf=conf,
        builder=messagebuilder.IRCMessageBuilder(),
        chanfilter=chanfilter,
        nick=conf.get('IRC_NICK'),
        autojoins=['#wikimedia-cloud'],
        host=conf.get('IRC_SERVER'),
        port=6697,
        ssl=True,
        password=conf.get('IRC_PASSWORD'),
        realname='wikibugs2',
        userinfo=('Wikibugs v2.1, https://tools.wmflabs.org/wikibugs/ ,' +
                  'running on ' + current_host),
        includes=[
            'irc3.plugins.core',
            'irc3.plugins.ctcp',
            'irc3.plugins.autojoins',
            __name__,  # this register MyPlugin
        ],
        ctcp={
            'finger': '{userinfo}',
            'source': '{userinfo}',
            'version': '{userinfo}',
            'userinfo': '{userinfo}',
            'ping': 'PONG',
        },
    )
    asyncio.Task(redisrunner(bot))
    bot.run()


if __name__ == '__main__':
    try:
        logger.info("Started")
        main()
    except Exception as e:
        logger.exception("Uncaught Exception:")
        raise
    finally:
        logger.info("Stopped")
