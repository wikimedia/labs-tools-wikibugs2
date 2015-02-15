#!/usr/bin/env python

import channelfilter
import json

chanfilter = channelfilter.ChannelFilter()
# An exception would have been raised if that wasn't the case
print('channels.yaml has valid syntax')


def assertEquals(expected, actual):
    assert expected == actual, "\nExpected: %s\nActual:   %s" % (expected, actual)

assertEquals(
    {'#mediawiki-feed', '#wikimedia-releng'},
    set(chanfilter.channels_for(['Continuous-Integration'])))

assertEquals(
    {'#mediawiki-feed', '#wikimedia-devtools', '#wikimedia-dev'},
    set(chanfilter.channels_for(['Phabricator'])))


json.load(open("config.json.example"))
print('config.json.example is valid json')

print('Acceptance tests passed')
