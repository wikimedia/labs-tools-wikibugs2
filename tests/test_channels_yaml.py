#!/usr/bin/env python
import json

import channelfilter
from tests.common import root


def test_channelfilter():
    chanfilter = channelfilter.ChannelFilter()
    # An exception would have been raised if that wasn't the case
    print('channels.yaml has valid syntax')

    assert {'#mediawiki-feed', '#wikimedia-releng'} == \
        set(chanfilter.channels_for(['Release-Engineering-Team']))
    assert {'#mediawiki-feed', '#wikimedia-dev', '#wikimedia-releng'} == \
        set(chanfilter.channels_for(['Phabricator']))
    assert {'#mediawiki-feed', '#wikimedia-collaboration', '#pywikibot'} == \
        set(chanfilter.channels_for(['Pywikibot-Flow']))


def test_config_json_is_valid_json():
    import sys
    print(sys.executable)
    json.load((root / "config.json.example").open())
