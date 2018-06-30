import sys
import requests

from wikibugs import Wikibugs2
from channelfilter import ChannelFilter
import configfetcher

conf = configfetcher.ConfigFetcher()
w = Wikibugs2(conf)
c = ChannelFilter()


print("\n\n\n\n\n\n\n\n")
page = requests.get(sys.argv[1]).text
tags = w.get_tags(page)

for tag in tags:
    print(tag, c.channels_for([tag]))
