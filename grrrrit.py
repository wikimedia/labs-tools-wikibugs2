#!/usr/bin/env python3

import json
import logging
import re
import subprocess
import os
import yaml

import messagebuilder
import configfetcher
import rqueue
from enum import Enum
from wblogging import LoggingSetupParser

IGNORED_USERS = ['L10n-bot', 'Libraryupgrader']
IGNORED_POSITIVE_VOTES = ['jenkins-bot', 'PipelineBot', 'SonarQube Bot']
JENKINS_USER = 'jenkins-bot'

logger = logging.getLogger('wikibugs.wb2-grrrrit')


class IncludeOwner(Enum):
    IF_NOT_USER = 1
    ALWAYS = 2


def trim_repo(repo: str) -> str:
    if repo.startswith('mediawiki/') or repo.startswith('operations/'):
        repo = repo.split('/', 1)[-1]
    return repo


def extract_bug(commit_msg: str):
    search = re.search(r'Bug: T(\d+)', commit_msg)
    if search:
        return 'T' + search.group(1)


def should_ignore_CI_comment(ret, event):
    """
    jenkins-bot and Pipeline bot get a special treatment: their comments are only reported
    in case an approval _is present_, and _changes_ to a _negative value_.
    The goal is to filter out post-commit events, code coverage comments, etc.

    :param event: The event to handle
    :return: Whether the event should be ignored or not.
    """
    if ret['user'] not in IGNORED_POSITIVE_VOTES:
        return False

    if 'approvals' not in event:
        return True

    if not any('oldValue' in approval and int(approval['value']) < 0
               for approval in event['approvals']):
        return True

    return False


# T239928
def change_is_WIP(event: dict) -> bool:
    return event.get('change', {}).get('wip', False)


def process_event(event: dict):
    user = event.get('uploader', {}).get('name') or event.get('author', {}).get('name')
    if user in IGNORED_USERS or change_is_WIP(event):
        return None

    ret = None
    if event['type'] == 'patchset-created':
        ps = 'PS' + str(event['patchSet']['number'])
        ret = process_simple(event, ps, 'uploader', IncludeOwner.IF_NOT_USER)
    elif event['type'] == 'comment-added':
        ret = process_simple(event, 'CR', 'author')

        if should_ignore_CI_comment(ret, event):
            return None

        comment = ''
        original_comment = event.get('comment')
        inline = 0

        if original_comment:
            inline_match = re.search(r'\((\d+) comments?\)', original_comment)
            if inline_match:
                try:
                    inline = int(inline_match.group(1))
                except ValueError:
                    pass
                # cheat! Get rid of (# comments) from the text
                original_comment = original_comment.replace(inline_match.group(0), '')
            comment = "\n".join(original_comment.split('\n')[1:]).strip().split('\n')[0].strip()
        if comment:
            comment = '"' + comment[:138] + '"'
        else:
            comment = event['change']['subject'][:140]
        ret['message'] = comment
        if ret['user'] == JENKINS_USER:
            ret['message'] = event['change']['subject']
        ret['inline'] = inline
        ret['approvals'] = {}

        if 'approvals' in event:
            for approval in event['approvals']:
                value = int(approval['value'])
                old_value = int(approval.get('oldValue', 0))

                if value == old_value:
                    # if the review value didn't change, don't mention the score
                    continue

                if approval['type'] == 'Verified' and value != 0:
                    ret['approvals']['V'] = value
                    if ret['user'] == JENKINS_USER and value == -1:
                        ret['user'] = 'jerkins-bot'  # For MaxSem
                elif approval['type'] == 'Code-Review' and value != 0:
                    ret['approvals']['C'] = value

    elif event['type'] == 'change-merged':
        ret = process_simple(event, 'Merged', 'submitter')
        if ret['user'] == JENKINS_USER and ret['owner'] in IGNORED_USERS:
            return None
        elif ret['user'] != JENKINS_USER:
            # Ignore any merges by anyone that is not jenkins-bot
            # This is always preceded by a C:2 by them, so we need not spam
            return None
    elif event['type'] == 'change-restored':
        ret = process_simple(event, 'Restored', 'restorer')
    elif event['type'] == 'change-abandoned':
        ret = process_simple(event, 'Abandoned', 'abandoner')

    return ret


def process_simple(event: dict, type_: str, user_property: str,
                   include_owner: IncludeOwner = IncludeOwner.ALWAYS) -> dict:
    ret = {
        'type': type_,
        'user': event[user_property]['name'],
        'message': event['change']['subject'],
        'repo': event['change']['project'],
        'branch': event['change']['branch'],
        # Use short URL form (T175929#6250620)
        'url': "https://gerrit.wikimedia.org/r/{}".format(event['change']['number']),
        'task': extract_bug(event['change']['commitMessage']),
    }

    owner = event['change']['owner']['name']
    if (
        (include_owner == IncludeOwner.ALWAYS) or
        (include_owner == IncludeOwner.IF_NOT_USER and ret['user'] != owner)
    ):
        ret['owner'] = owner

    return ret


def build_message(processed: dict) -> str:
    helper = messagebuilder.IRCMessageBuilder().ircformat
    text = '({})'.format(helper(processed['type'], foreground='green'))
    text += ' {}:'.format(helper(processed['user'], foreground='teal', style='bold'))
    if 'approvals' in processed and processed['approvals']:
        def format_approval(value: int) -> str:
            if value == 1:
                return helper("+1", foreground='green')
            elif value == 2:
                return helper("+2", foreground='green', style='bold')
            elif value == -1:
                return helper("-1", foreground='red')
            else:  # -2
                return helper(str(value), foreground='red', style='bold')

        text += ' ['
        has_c = 'C' in processed['approvals']
        has_v = 'V' in processed['approvals']
        if has_v:
            text += 'V: {}'.format(format_approval(processed['approvals']['V']))
        if has_v and has_c:
            text += ' '
        if has_c:
            text += 'C: {}'.format(format_approval(processed['approvals']['C']))
        text += ']'
    text += ' {}'.format(processed['message'])
    if 'inline' in processed and processed['inline']:
        text += ' ({} {})'.format(
            helper(str(processed['inline']), foreground='green', style='bold'),
            'comments' if processed['inline'] > 1 else 'comment'
        )
    text += ' [{}]'.format(trim_repo(processed['repo']))
    if processed['branch'] not in ('master', 'production'):
        text += ' ({})'.format(processed['branch'])
    text += ' -'
    text += ' {}'.format(helper(processed['url'], foreground='teal'))
    if processed['task']:
        text += ' (https://phabricator.wikimedia.org/{})'.format(processed['task'])
    if 'owner' in processed:
        text += ' (owner: {})'.format(helper(processed['owner'], foreground='teal', style='bold'))

    return text


def channel_filter(repo: str, branch: str) -> set:
    # TODO use the channelfilter module
    with open(os.path.join(os.path.dirname(__file__), 'gerrit-channels.yaml')) as f:
        data = yaml.safe_load(f)
    channels = set()
    for channel in data['channels']:
        repos = data['channels'][channel]
        for repo_re, filters in repos.items():
            if re.match(repo_re, repo):
                if filters:
                    if not re.match(filters['branch'], branch):
                        continue
                channels.add(channel)

    if not channels:
        channels.add(data['default-channel'])

    channels.add(data['firehose-channel'])
    return channels


def main():
    conf = configfetcher.ConfigFetcher()
    queue = rqueue.RedisQueue(
        conf.get('REDIS_QUEUE_NAME'),
        conf.get('REDIS_HOST')
    )
    ssh = subprocess.Popen(
        ['ssh', 'suchabot@gerrit.wikimedia.org',
         '-i', os.path.join(os.path.dirname(__file__), 'id_rsa'),
         '-p', '29418',
         'gerrit', 'stream-events'
         ],
        shell=False,
        bufsize=1,  # line buffered
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    logger.info('Opened SSH connection')

    for line in ssh.stdout:
        logger.info("%s: %s", "stream-events", line.decode())
        parsed = json.loads(line.decode())
        processed = process_event(parsed)
        if processed:
            logger.info("%s: %s", "processed", json.dumps(processed))
            try:
                msg = build_message(processed)
                channels = list(channel_filter(processed['repo'], processed['branch']))
                queue.put({'raw': True, 'msg': msg, 'channels': channels})
                logger.info("%s: '%s' to [%s]", "message", msg, ", ".join(channels))
            except KeyboardInterrupt:
                raise
            except:
                logger.exception('Error queuing message')
        ssh.stdout.flush()


if __name__ == '__main__':
    parser = LoggingSetupParser(
        description='Sends events from Gerrit to IRC'
    )
    parser.parse_args()

    while True:
        try:
            main()
        except KeyboardInterrupt:
            raise
        except:
            logger.exception('Error, probably SSH connection dropped.')
