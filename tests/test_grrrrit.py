import json
import unittest
from pathlib import Path

import grrrrit
from grrrrit import IncludeOwner

root = Path(__file__).parent.parent
data_path = root / "tests" / "data" / "stream_events"


def process_events(events_list):
    results = []
    for event in events_list:
        processed_event = grrrrit.process_event(event)
        if processed_event:
            results.append(processed_event)
    return results


def test_new_patchset_created():
    events = json.load((data_path / "new_patchset_created.json").open())
    processed = process_events(events)

    assert processed[0] == {
        'type': 'PS1',
        'user': 'RealName 1',
        'message': 'test',
        'branch': 'master',
        'repo': 'test',
        'task': None,
        'url': 'https://gerrit.git.wmflabs.org/r/2001'}


class TestProcessSimple(unittest.TestCase):
    def setUp(self):
        self.event = {
            "uploader": {"name": "UserName"},
            "change": {
                "project": "test",
                "branch": "master",
                "subject": "test",
                "url": "https://gerrit.git.wmflabs.org/r/2001",
                "commitMessage": "test\n\nChange-Id: I5a0210ada1104a378c2ecbc1dc7ec6c683d0eccd\n",
                "owner": {"name": "UserName"},
            }
        }

    def test_basic_full(self):
        result = grrrrit.process_simple(self.event, "test_event", "uploader")
        assert result['type'] == 'test_event'
        assert result['message'] == 'test'
        assert result['repo'] == 'test'
        assert result['branch'] == 'master'
        assert result['url'] == 'https://gerrit.git.wmflabs.org/r/2001'
        assert result['user'] == 'UserName'
        assert result['owner'] == 'UserName'
        assert result['task'] is None

    def test_bug_url(self):
        """Test that the _first_ included __Bug__ is included in the message """
        self.event['change']['commitMessage'] = """test

Task: T12344
Bug: T12345
Bug: T12346
Change-Id: I5a0210ada1104a378c2ecbc1dc7ec6c683d0eccd
"""
        result = grrrrit.process_simple(self.event, "test_event", "uploader")

        assert result['task'] == "T12345"

    def test_hide_if_user_is_owner(self):
        result = grrrrit.process_simple(self.event, "test_event", "uploader", IncludeOwner.IF_NOT_USER)
        assert 'owner' not in result

    def test_include_owner_if_different(self):
        self.event['uploader']['name'] = 'OtherUser'
        result = grrrrit.process_simple(self.event, "test_event", "uploader", IncludeOwner.IF_NOT_USER)
        assert result['user'] == 'OtherUser'
        assert result['owner'] == 'UserName'
