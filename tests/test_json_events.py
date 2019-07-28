import json
from pathlib import Path

import grrrrit


root = Path(__file__).parent.parent
data_path = root / "tests" / "data" / "stream_events"


def process_events(events_list):
    results = []
    for event in events_list:
        processed_event = grrrrit.process_event(event)
        if processed_event:
            results.append(processed_event)
    return results


def process_events_file(filename):
    events = json.load(filename.open())
    processed = process_events(events)
    return processed


def test_new_change():
    messages = process_events_file(data_path / "new_change.json")

    assert len(messages) == 1
    assert messages[0] == {
        'type': 'PS1',
        'user': 'RealName 1',
        'message': 'test',
        'branch': 'master',
        'repo': 'test',
        'task': None,
        'url': 'https://gerrit.git.wmflabs.org/r/2001'}


def test_new_patchset():
    messages = process_events_file(data_path / "patchset_modified.json")

    assert len(messages) == 1

    assert messages[0] == {
        'type': 'PS3',
        'branch': 'master',
        'url': 'https://gerrit.wikimedia.org/r/429546',
        'message': 'Testing draft changes',  # noqa
        'user': 'RealName 1',
        'task': None,
        'repo': 'test/gerrit-ping'
    }


def test_jenkins_verified_plus_2():
    """Jenkins' V+2 messages are not reported as they are not actionable"""
    messages = process_events_file(data_path / "jenkins_v+2.json")

    assert len(messages) == 0


def test_jenkins_verified_minus_1():
    """Jenkins' V-1 messages are reported as Jerkins-bot"""
    messages = process_events_file(data_path / "jenkins_v-1.json")

    assert len(messages) == 1
    assert messages[0] == {
        'type': 'CR',
        'approvals': {'V': -1},
        'inline': 0,
        'branch': 'master',
        'url': 'https://gerrit.wikimedia.org/r/443220',
        'message': 'Ignore wips when creating a patchset',  # noqa
        'owner': 'RealName 2',
        'user': 'jerkins-bot',
        'task': None,
        'repo': 'labs/tools/wikibugs2'
    }


def test_cr_plus_1():
    messages = process_events_file(data_path / "cr+1.json")

    assert len(messages) == 1
    assert messages[0] == {
        'type': 'CR',
        'approvals': {'C': 1},
        'inline': 0,
        'branch': 'master',
        'url': 'https://gerrit.wikimedia.org/r/429546',
        'message': 'Testing draft changes',  # noqa
        'owner': 'RealName 1',
        'user': 'RealName 1',
        'task': None,
        'repo': 'test/gerrit-ping'
    }


def test_cr_plus_2():
    messages = process_events_file(data_path / "cr+2.json")

    assert len(messages) == 1
    assert messages[0] == {
        'type': 'CR',
        'approvals': {'C': 2},
        'inline': 0,
        'branch': 'master',
        'url': 'https://gerrit.wikimedia.org/r/450447',
        'message': 'Refactor json-loaded tests',  # noqa
        'owner': 'RealName 1',
        'user': 'RealName 1',
        'task': None,
        'repo': 'labs/tools/wikibugs2'
    }


def test_gate_submit_merge():
    """Gate and submit messages are ignored, unless resulting in V-1. Only the final merge is reported."""
    messages = process_events_file(data_path / "gate-submit-merge.json")

    assert len(messages) == 1
    assert messages[0] == {
        'type': 'Merged',
        'branch': 'master',
        'url': 'https://gerrit.wikimedia.org/r/450446',
        'message': 'Add simple anonimization script for stream_events data',  # noqa
        'owner': 'RealName 1',
        'user': 'jenkins-bot',
        'task': None,
        'repo': 'labs/tools/wikibugs2'
    }


def test_post_merge_build():
    messages = process_events_file(data_path / "post-merge-build.json")

    assert len(messages) == 0
