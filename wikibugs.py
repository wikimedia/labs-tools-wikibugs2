#!/usr/bin/env python

import functools
import logging
import phabricator
import time
import json
import configfetcher
import rqueue
from wblogging import LoggingSetupParser

USER_AGENT = 'Wikibugs v2.1, https://www.mediawiki.org/wiki/Wikibugs'

parser = LoggingSetupParser(
    description="Read bugs from redis, format them and send them to irc",
)
parser.add_argument('--raise', dest='raise_errors', action='store_true',
                    help="Raise exceptions instead of just logging them")
parser.add_argument('files', metavar='file', nargs='*',
                    help="XACT files to parse (listen to phabricator otherwise)")
parser.add_argument('--ask', dest='ask_before_push', action='store_true',
                    help='Ask before pushing change to redis')
args = parser.parse_args()

logging.getLogger('requests').setLevel(logging.INFO)

logger = logging.getLogger('wikibugs.wb2-phab')


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
            self.conf.get('PHAB_CERT'),
            user_agent=USER_AGENT
        )
        self.rqueue = rqueue.RedisQueue(
            conf.get('REDIS_QUEUE_NAME'),
            conf.get('REDIS_HOST')
        )
        self.poll_last_seen_chrono_key = 0
        self.raise_errors = False

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

        for event in sorted(events.values(), key=lambda x: int(x['chronologicalKey'])):
            key = int(event['chronologicalKey'])
            if key > self.poll_last_seen_chrono_key:
                self.process_event(event)
                self.poll_last_seen_chrono_key = key

    def phid_info(self, phid):
        info = self.phab.request('phid.query', {
            'phids': [phid]
        })
        logger.debug("phid_info(%s): %s", phid, info)
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
        logger.debug('maniphest.info for %r = %s', task_id, json.dumps(info))
        return info

    @functools.lru_cache(maxsize=200)
    def project_info(self, phid):
        info = self.phab.request('project.search', {
            'constraints': {
                'phids': [phid],
            },
        })['data'][0]
        logger.debug('project.search for %r = %s', phid, json.dumps(info))
        return info

    @functools.lru_cache(maxsize=200)
    def cached_phid_info(self, phid):
        """
        Same thing as phid_info, but
        cached
        """
        return self.phid_info(phid)

    def get_transaction_info(self, task_id, transaction_phids):
        """
        :param task_id: T###
        :type task_id: basestring
        :param transaction_phids: PHID-XACT-TASK-* stuff
        :type transaction_phids: list
        """
        task_id = int(task_id[1:])
        info = self.phab.request('maniphest.gettasktransactions', {
            'ids': [task_id]
        })
        transactions = {}
        for trans in list(info.values())[0]:
            if trans['transactionPHID'] in transaction_phids:
                ttype = trans['transactionType']
                transactions[ttype] = {
                    'old': trans['oldValue'],
                    'new': trans['newValue'],
                    'anchor': trans['transactionID'],
                }
                if trans['comments'] is not None:
                    transactions[ttype]['comments'] = trans['comments']
                if 'core.create' in trans['meta']:
                    # This was part of the initial object creation.
                    # Force anchor to "0" so bare link will be used later
                    transactions[ttype]['anchor'] = '0'
        logger.debug('get_transaction_info(%r,%r) = %s', task_id, transaction_phids, json.dumps(transactions))
        return transactions

    def get_tags(self, task_info):
        """
        :param task_info: Data from the maniphest.info API
        :type task_info: dict
        """
        alltags = {}
        logger.debug('get_tags(%s)', json.dumps(task_info))

        for phid in task_info['projectPHIDs']:
            tag = self.project_info(phid)
            phid_info = self.cached_phid_info(phid)

            name = tag['fields']['name']
            alltags[name] = {
                'shade': tag['fields']['color']['key'],
                'disabled': phid_info['status'] == 'closed',
                'tagtype': tag['fields']['icon']['icon'][3:],
                'uri': phid_info['uri'],
            }
        return alltags

    def guess_best_anchor(self, transactions):
        """
        :param transactions: simplified transaction info
        :type transactions: list(dict)
        :returns basestring
        """
        logger.debug('guess_best_anchor(%s)', transactions)
        # Our current theory is that the lowest (oldest) transaction id in the
        # set is what Phorge will be using as an anchor id in the rendered
        # HTML. We know however that this is only true after discarding some
        # transaction types, so it is a fragile heuristic at best.
        anchors = [trans['anchor'] for trans in transactions.values()]
        min_anchor = sorted(anchors, key=lambda x: int(x))[0]
        if min_anchor != '0':
            return f"#{min_anchor}"
        return ""

    def get_type_from_phid(self, phid):
        """

        :param phid: PHID-TASK-* or PHID-CMIT-*, etc
        :return: str
        """
        return phid.split('-')[1]

    def process_event(self, event_info):
        """
        :type event_info: dict
        """
        phid_type = self.get_type_from_phid(event_info['data']['objectPHID'])
        if phid_type != 'TASK':  # Only handle Maniphest Tasks for now
            logger.debug('Skipping %s, it is of type %s', event_info['data']['objectPHID'], phid_type)
            return

        if 'transactionPHIDs' not in event_info['data']:
            logger.debug('Skipping %s, does not contain transactions', event_info['data']['objectPHID'])
            # If there are no transactions, it's something weird like tokens
            return

        logger.debug('Processing %s', json.dumps(event_info))

        phid_info = self.phid_info(event_info['data']['objectPHID'])
        task_info = self.maniphest_info(phid_info['name'])

        transactions = self.get_transaction_info(phid_info['name'], event_info['data']['transactionPHIDs'])
        ignored = [
            'core:columns',         # Column changes, see T1204
            'core:edit-policy',     # Edit policy changed
            'core:file',            # Attached/removed/modified file
            'core:inlinestate',     # Changed inline comment state
            'core:interact-policy'  # Interaction policy changed
            'core:join-policy',     # Join policy changed
            'core:space',           # Moved to a different space
            'core:subscribers',     # CC updates
            'core:subtype',         # Subtype changes
            'core:view-policy',     # View policy changed
            'token:give',           # Adding a token
        ]
        removed_types = []
        for event_type in ignored:
            if event_type in transactions:
                removed_types.append(event_type)
                transactions.pop(event_type)

        if not transactions:
            # We removed everything, skip.
            logging.debug(
                "Skipping %s which only has event types: %s",
                event_info['data']['transactionPHIDs'],
                ', '.join(removed_types),
            )
            return

        anchor = self.guess_best_anchor(transactions)
        projects = self.get_tags(task_info)

        # Start sorting this into things we care about...
        useful_event_metadata = {
            'url': phid_info['uri'] + anchor,
            'projects': projects,
            'user': self.get_user_name(event_info['authorPHID']),
        }

        if 'title' in transactions:
            useful_event_metadata['title'] = transactions['title']['new']
            if transactions['title']['old'] is None:
                useful_event_metadata['new'] = True
        else:
            # Technically there's a race condition if the title is changed
            # in another event before our API request is made, but meh
            # Name is in the format "T123: FooBar", so get rid of the prefix
            useful_event_metadata['title'] = phid_info['fullName'].split(':', 1)[1].strip()
        if 'core:comment' in transactions and 'comments' in transactions['core:comment']:
            useful_event_metadata['comment'] = transactions['core:comment']['comments']
        for _type in ['status', 'priority']:
            if _type in transactions:
                useful_event_metadata[_type] = transactions[_type]
        if 'status' in useful_event_metadata and useful_event_metadata['status']['old'] is None:
            useful_event_metadata['new'] = True
            useful_event_metadata['url'] = useful_event_metadata['url'].split('#')[0]
        if 'reassign' in transactions:
            trans = transactions['reassign']
            info = {}
            for _type in ['old', 'new']:
                if trans[_type] is not None:
                    info[_type] = self.get_user_name(trans[_type])
                else:
                    info[_type] = None
            useful_event_metadata['assignee'] = info

        logger.debug(useful_event_metadata)
        if not args.ask_before_push or \
                input('Push? (y/N)').lower().strip() == 'y':
            self.rqueue.put(useful_event_metadata)

    def dump_error(self, error_type, e, event_info):
        open("/data/project/wikibugs/errors/" + error_type + "/" + event_info['data']['objectPHID'], "w").write(
            repr(event_info) + "\n" + repr(e)
        )


if __name__ == '__main__':
    bugs = Wikibugs2(
        configfetcher.ConfigFetcher()
    )
    # Usage:
    # python -i wikibugs.py ~/errors/XACT-anchor/PHID-TASK-qmkysswakxnzzausyzlv
    # then import pdb; pdb.pm() to enter the debugger

    bugs.raise_errors = args.raise_errors
    for file in args.files:
        logger.info("Processing %s", file)
        from collections import OrderedDict  # noqa
        bugs.process_event(eval(open(file).readline()))

    logger.info("Starting polling cycle")
    try:
        while 1:
            bugs.poll()
            time.sleep(1)
    except Exception:
        logger.exception("Uncaught Exception in polling cycle:")
        raise
    finally:
        logger.info("Shutting down")
