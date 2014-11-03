#!/usr/bin/env python

from dogpile.cache import make_region
import json
import phabricator
import requests
import time

import configfetcher
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
    def __init__(self, conf):
        """
        :param conf: Config
        :type conf: configfetcher.ConfigFetcher
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
                #print trans
                transactions[trans['transactionType']] = {
                    'old': trans['oldValue'],
                    'new': trans['newValue'],
                }
                if trans['comments'] is not None:
                    transactions[trans['transactionType']]['comments'] = trans['comments']

        return transactions

    def process_event(self, event_info):
        """
        :type event_info: dict
        """
        timestamp = str(event_info['epoch'])
        phid_info = self.phid_info(event_info['data']['objectPHID'])
        if phid_info['type'] != 'TASK':  # Only handle Maniphest Tasks for now
            return
        if phid_info['uri'] != 'https://phab-01.wmflabs.org/T84':
            return
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
            if transactions['title']['old'] is None:
                useful_event_metadata['new'] = True
        else:
            # Technically there's a race condition if the title is changed
            # in another event before our API request is made, but meh
            # Name is in the format "T123: FooBar", so get rid of the prefix
            useful_event_metadata['title'] = phid_info['fullName'].split(':', 1)[1].strip()
        if 'core:comment' in transactions:
            useful_event_metadata['comment'] = transactions['core:comment']['comments']
        if 'priority' in transactions:
            useful_event_metadata['priority'] = transactions['priority']
            pass
        if 'reassign' in transactions:
            trans = transactions['reassign']
            info = {}
            for _type in ['old', 'new']:
                if trans[_type] is not None:
                    info[_type] = self.get_user_name(trans[_type])
            useful_event_metadata['assignee'] = info

        print useful_event_metadata
        #self.rqueue.put(useful_event_metadata)



if __name__ == '__main__':
    bugs = Wikibugs2(conf)
    bugs.poll()
