#!/usr/bin/env python

from dogpile.cache import make_region
import json
import phabricator
import requests
import time

import configfetcher
import messagebuilder
import rqueue

conf = configfetcher.ConfigFetcher()

region = make_region().configure(
    'dogpile.cache.redis',
    arguments={
        'host': conf.get('REDIS_HOST'),
        'port': 6379,
        'db': 0,
        'redis_expiration_time': 60*60*2,   # 2 hours
        'distributed_lock': True
    }
)


class Wikibugs2(object):
    def __init__(self, conf, builder):
        """
        :param conf: Config
        :type conf: configfetcher.ConfigFetcher
        :param builder: Converts event info to a string
        :type builder: messagebuilder.IRCMessageBuilder
        """
        self.conf = conf
        self.phab = phabricator.Phabricator(
            self.conf.get('PHAB_HOST'),
            self.conf.get('PHAB_USER'),
            self.conf.get('PHAB_CERT')
        )
        self.rqueue = rqueue.RedisQueue(
            conf.get('REDIS_QUEUE_NAME'),
            conf.get('REDIS_HOST')
        )
        self.builder = builder

    @region.cache_on_arguments()
    def get_user_name(self, phid):
        """
        :param phid: A PHID- thingy representing a user
        :type phid: basestring
        """
        info = self.phab.request('user.query', {
            'phids': [phid]
        })
        return info[0]['userName']

    def get_project_name(self, phid):
        return self.cached_phid_info(phid)['name']

    def poll(self):
        events = self.phab.request('feed.query', {
            'view': 'data'
        })
        for event in events.values():
            self.process_event(event)

    def phid_info(self, phid):
        info = self.phab.request('phid.query', {
            'phids': [phid]
        })
        return info.values()[0]

    def maniphest_info(self, task_id):
        """
        :param task_id: T###
        :type task_id: basestring
        """
        task_id = int(task_id[1:])
        info = self.phab.request('maniphest.info', {
            'task_id': task_id
        })
        return info

    @region.cache_on_arguments()
    def cached_phid_info(self, phid):
        """
        Same thing as phid_info, but
        cached
        """
        return self.phid_info(phid)

    def get_transaction_info(self, task_id, timestamp):
        """
        :param task_id: T###
        :type task_id: basestring
        :param timestamp: "epoch timestamp"
        :type timestamp: basestring
        """
        task_id = int(task_id[1:])
        info = self.phab.request('maniphest.gettasktransactions', {
            'ids': [task_id]
        })
        transactions = {}
        for trans in info.values()[0]:
            if trans['dateCreated'] == timestamp:  # Yeah, this is a hack, but it works
                transactions[trans['transactionType']] = {
                    'old': trans['oldValue'],
                    'new': trans['newValue'],
                    'comments': trans['comments'],
                }

        return transactions

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

    def process_event(self, event_info):
        """
        :type event_info: dict
        """
        timestamp = str(event_info['epoch'])
        phid_info = self.phid_info(event_info['data']['objectPHID'])
        if phid_info['type'] != 'TASK':  # Only handle Maniphest Tasks for now
            return
        #if phid_info['uri'] != 'https://phab-01.wmflabs.org/T47':
        #    return
        task_info = self.maniphest_info(phid_info['name'])
        # Start sorting this into things we care about...
        useful_event_metadata = {
            'url': phid_info['uri'],
            'projects': [self.get_project_name(phid) for phid in task_info['projectPHIDs']],
            'user': self.get_user_name(event_info['authorPHID']),
        }
        transactions = self.get_transaction_info(phid_info['name'], timestamp)
        if 'ccs' in transactions and len(transactions) == 1:
            # Ignore any only-CC updates
            return
        if 'title' in transactions:
            useful_event_metadata['title'] = transactions['title']['new']
            pass
        else:
            # Technically there's a race condition if the title is changed
            # in another event before our API request is made, but meh
            # Name is in the format "T123: FooBar", so get rid of the prefix
            useful_event_metadata['title'] = phid_info['fullName'].split(':', 1)[1].strip()
        if 'core:comment' in transactions:
            useful_event_metadata['comment'] = transactions['core:comment']['comments']
        print useful_event_metadata
        message = self.builder.build_message(useful_event_metadata)
        channels = self.get_channels_for_projects(useful_event_metadata['projects'])
        self.rqueue.put({
            'channels': channels,
            'text': message,
        })



if __name__ == '__main__':
    bugs = Wikibugs2(
        conf,
        messagebuilder.IRCMessageBuilder()
    )
    bugs.poll()
