import pytest

import grrrrit
from grrrrit import IncludeOwner


@pytest.fixture()
def event():
    return {
        "uploader": {"name": "UserName"},
        "change": {
            "project": "test",
            "branch": "master",
            "subject": "test",
            "number": "2001",
            "url": "https://gerrit.git.wmflabs.org/r/2001",
            "commitMessage": "test\n\nChange-Id: I5a0210ada1104a378c2ecbc1dc7ec6c683d0eccd\n",
            "owner": {"name": "UserName"},
        }
    }


def test_basic_full(event):
    result = grrrrit.process_simple(event, "test_event", "uploader")
    assert result['type'] == 'test_event'
    assert result['message'] == 'test'
    assert result['repo'] == 'test'
    assert result['branch'] == 'master'
    assert result['url'] == 'https://gerrit.wikimedia.org/r/2001'
    assert result['user'] == 'UserName'
    assert result['owner'] == 'UserName'
    assert result['task'] is None


def test_bug_url(event):
    """Test that the _first_ included __Bug__ is included in the message """
    event['change']['commitMessage'] = """test

Task: T12344
Bug: T12345
Bug: T12346
Change-Id: I5a0210ada1104a378c2ecbc1dc7ec6c683d0eccd
"""
    result = grrrrit.process_simple(event, "test_event", "uploader")

    assert result['task'] == "T12345"


def test_hide_if_user_is_owner(event):
    result = grrrrit.process_simple(event, "test_event", "uploader", IncludeOwner.IF_NOT_USER)
    assert 'owner' not in result


def test_include_owner_if_different(event):
    event['uploader']['name'] = 'OtherUser'
    result = grrrrit.process_simple(event, "test_event", "uploader", IncludeOwner.IF_NOT_USER)
    assert result['user'] == 'OtherUser'
    assert result['owner'] == 'UserName'
