#!/usr/bin/env python

import functools
import phabricator
import time

import configfetcher
import rqueue

conf = configfetcher.ConfigFetcher()


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
        self.poll_last_seen_chrono_key = 0

    @functools.lru_cache(maxsize=200)
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
        if self.poll_last_seen_chrono_key == 0:
            # First time, get the latest event and start from there
            latest = list(self.phab.request('feed.query', {
                'limit': '1',
            }).values())[0]
            self.poll_last_seen_chrono_key = int(latest['chronologicalKey'])

        events = self.phab.request('feed.query', {
            'view': 'data',
            'before': self.poll_last_seen_chrono_key,
        })

        if not events:
            # PHP bug, what should be {} is actually []
            return
        events = list(events.values())
        # Events are in the order of most recent first to oldest, so reverse!
        events.reverse()
        for event in events:
            key = int(event['chronologicalKey'])
            if key > self.poll_last_seen_chrono_key:
                self.process_event(event)
                self.poll_last_seen_chrono_key = key

    def phid_info(self, phid):
        info = self.phab.request('phid.query', {
            'phids': [phid]
        })
        return list(info.values())[0]

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

    @functools.lru_cache(maxsize=200)
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
        for trans in list(info.values())[0]:
            if trans['dateCreated'] == timestamp:  # Yeah, this is a hack, but it works
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
            useful_event_metadata['comment'] = transactions['core:comment'].get('comments', 'Removed.')
        for _type in ['status', 'priority']:
            if _type in transactions:
                useful_event_metadata[_type] = transactions[_type]
        if 'status' in useful_event_metadata and useful_event_metadata['status']['old'] is None:
            useful_event_metadata['new'] = True
        if 'reassign' in transactions:
            trans = transactions['reassign']
            info = {}
            for _type in ['old', 'new']:
                if trans[_type] is not None:
                    info[_type] = self.get_user_name(trans[_type])
                else:
                    info[_type] = None
            useful_event_metadata['assignee'] = info

        print(useful_event_metadata)
        self.rqueue.put(useful_event_metadata)


if __name__ == '__main__':
    bugs = Wikibugs2(conf)
    while 1:
        bugs.poll()
        time.sleep(1)
