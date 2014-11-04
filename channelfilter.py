import yaml

class ChannelFilter(object):
    def __init__(self, config):
        self.config = config
        print config

    def channels_for(self, project):
        channels = set()
        for channel in self.config['channels']:
            if project in self.config['channels'][channel]:
                channels.add(channel)
                continue
        channels.add(self.config['firehose-channel'])
        print channels
        return channels