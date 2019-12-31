#!/usr/bin/env python

import functools
import logging
import phabricator
import time
import json
from bs4 import BeautifulSoup
import configfetcher
import rqueue
from wblogging import LoggingSetupParser

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
            self.conf.get('PHAB_CERT')
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
        logger.debug('maniphest.info for %r = %s' % (task_id, json.dumps(info)))
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
                transactions[trans['transactionType']] = {
                    'old': trans['oldValue'],
                    'new': trans['newValue'],
                }
                if trans['comments'] is not None:
                    transactions[trans['transactionType']]['comments'] = trans['comments']
        logger.debug('get_transaction_info(%r,%r) = %s' % (task_id, transaction_phids, json.dumps(transactions)))
        return transactions

    def get_task_page(self, url):
        return self.phab.req_session.get(url).text

    def get_tags(self, task_page):
        soup = BeautifulSoup(task_page, features='html.parser')
        alltags = {}

        for tag in soup.findAll(class_='phabricator-handle-tag-list-item'):
            taglink = tag.find('a', class_='phui-tag-view')
            if not taglink:
                continue

            marker = taglink.find('span', class_='phui-icon-view')

            classes = taglink['class'] + marker['class']

            disabled = "phui-tag-disabled" in classes
            tagtype = [cls.split("-")[1] for cls in classes if cls.startswith("fa-")][0]
            uri = taglink['href']
            name = taglink.text
            alltags[name] = {'shade': "blue",
                             'disabled': disabled,
                             'tagtype': tagtype,
                             'uri': uri}
        return alltags

    def get_anchors_for_task(self, task_page):
        """
        :param url: url to task
        :type url: basestring
        :returns dict(phid => anchor)
        """
        data_dict_str = task_page.split(
            '<script type="text/javascript">JX.Stratcom.mergeData(0,'
        )[1].split(
            ");\nJX.onload"
        )[0]

        data_dict = json.loads(data_dict_str)
        return {x[u'phid']: x[u'anchor'] for x in data_dict if u'phid' in x and u'anchor' in x}

    def get_lowest_anchor_for_task_and_XACTs(self, task_page, XACTs):
        """
        :param url: url to task
        :type url: basestring
        :param XACTs: list of XACT phids to look up anchors for
        :type XACTs: list(basestring)
        :returns dict(phid => anchor)
        """
        anchor_dict = self.get_anchors_for_task(task_page)
        anchors = [anchor_dict.get(phid, None) for phid in XACTs]
        anchors = [anchor for anchor in anchors if anchor]

        if anchors:
            return "#{anchor}".format(anchor=sorted(anchors, key=lambda x: int(x))[0])

        # if no anchors could be found, return the highest-numbered anchor we /can/ find
        anchors = sorted(anchor_dict.values(), key=lambda x: int(x))
        if anchors:
            return "#{anchor}".format(anchor=sorted(anchors, key=lambda x: int(x))[0])
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
            logger.debug('Skipping %s, it is of type %s' % (event_info['data']['objectPHID'], phid_type))
            return
        logger.debug('Processing %s' % json.dumps(event_info))

        phid_info = self.phid_info(event_info['data']['objectPHID'])
        task_info = self.maniphest_info(phid_info['name'])

        # try to get the (lowest) anchor for this change
        task_page = self.get_task_page(phid_info['uri'])
        try:
            anchor = self.get_lowest_anchor_for_task_and_XACTs(
                task_page, event_info['data']['transactionPHIDs']
            )
        except Exception as e:
            logger.exception("Could not retrieve anchor for %s" % event_info['data']['transactionPHIDs'])
            if self.raise_errors:
                raise
            open("/data/project/wikibugs/errors/XACT-anchor/" + event_info['data']['objectPHID'], "w").write(
                repr(event_info) + "\n" + repr(e)
            )
            anchor = ""

        try:
            projects = self.get_tags(task_page)
        except Exception as e:
            logger.exception("Could not retrieve tags for %s" % event_info['data']['transactionPHIDs'])
            if self.raise_errors:
                raise
            open("/data/project/wikibugs/errors/scrape-tags/" + event_info['data']['objectPHID'], "w").write(
                repr(event_info) + "\n" + repr(e)
            )
            projects = [self.get_project_name(phid) for phid in task_info['projectPHIDs']]

        # Start sorting this into things we care about...
        useful_event_metadata = {
            'url': phid_info['uri'] + anchor,
            'projects': projects,
            'user': self.get_user_name(event_info['authorPHID']),
        }

        if 'transactionPHIDs' not in event_info['data']:
            # If there are no transactions, it's something weird like tokens
            return
        transactions = self.get_transaction_info(phid_info['name'], event_info['data']['transactionPHIDs'])
        ignored = [
            'core:subscribers',  # Ignore any only-CC updates
            'core:columns',  # Ignore column changes, see T1204
        ]
        removed = []
        for event in ignored:
            if event in transactions:
                removed.append(event)
                transactions.pop(event)

        if not transactions:
            # We removed everything, skip.
            logging.debug("Skipping {PHID} which only has an event of type {ttype}".format(
                PHID=event_info['data']['transactionPHIDs'],
                ttype=', '.join(removed),
            ))
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


if __name__ == '__main__':
    bugs = Wikibugs2(
        configfetcher.ConfigFetcher()
    )
    # Usage:
    # python -i wikibugs.py ~/errors/XACT-anchor/PHID-TASK-qmkysswakxnzzausyzlv
    # then import pdb; pdb.pm() to enter the debugger

    bugs.raise_errors = args.raise_errors
    for file in args.files:
        logger.info("Processing {f}".format(f=file))
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
