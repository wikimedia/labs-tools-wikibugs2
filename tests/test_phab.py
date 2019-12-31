# encoding: utf-8
from collections import OrderedDict
import json
from pathlib import Path
import urllib.parse

import pytest
import requests_mock

import configfetcher
import phabricator
import wikibugs

root = Path(__file__).parent.parent


class WikibugsFixture:
    def __init__(self):
        self.events = []
        self.wikibugs = wikibugs.Wikibugs2(
            configfetcher.ConfigFetcher(str(root / "config.json.example"))
        )
        self.wikibugs.process_event = lambda event: self.events.append(event)

    def poll(self):
        self.wikibugs.poll()


@pytest.fixture()
def bugs():
    return WikibugsFixture()


def parse_request(request):
    decoded = OrderedDict(urllib.parse.parse_qsl(request.text))
    assert decoded['output'] == 'json'
    return json.loads(decoded['params'])


def conduit_connect_1(request, context):
    return {'result': {'sessionKey': 'key', 'connectionID': 1}}


def feed_query_initial(request, context):
    content = parse_request(request)
    assert int(content['limit']) == 1
    assert 'before' not in content
    return json.loads(r"""{"result":{"PHID-STRY-cdxv7sji5d7wnjmiuqgv":{"class":"PhabricatorApplicationTransactionFeedStory","epoch":1577802875,"authorPHID":"PHID-USER-pzp7mdlx7otgdlggnyhh","chronologicalKey":"6776611750075855743","data":{"objectPHID":"PHID-TASK-rnay3rzefpqhoaqm3guo","transactionPHIDs":{"PHID-XACT-TASK-5esu7y3d7evlsi2":"PHID-XACT-TASK-5esu7y3d7evlsi2"}}}},"error_code":null,"error_info":null}""")  # noqa


def feed_query_second(request, context):
    content = parse_request(request)
    assert content['before'] == 6776611750075855743
    assert content['view'] == 'data'
    return json.loads(r"""{"result":[],"error_code":null,"error_info":null}""")


def feed_query_third(request, context):
    content = parse_request(request)
    assert content['before'] == 6776611750075855743
    assert content['view'] == 'data'
    return json.loads(r"""{"result":{"PHID-STRY-etrbfg7qqflcsoexaxqr":{"class":"PhabricatorApplicationTransactionFeedStory","epoch":1577804347,"authorPHID":"PHID-USER-idceizaw6elwiwm5xshb","chronologicalKey":"6776618070283272953","data":{"objectPHID":"PHID-TASK-he2h6hqmwrdrav3cxqew","transactionPHIDs":{"PHID-XACT-TASK-k6asmqpfv2t37tp":"PHID-XACT-TASK-k6asmqpfv2t37tp"}}},"PHID-STRY-x6pr64eeimmcjl3jbsay":{"class":"PhabricatorApplicationTransactionFeedStory","epoch":1577804344,"authorPHID":"PHID-USER-idceizaw6elwiwm5xshb","chronologicalKey":"6776618060350723377","data":{"objectPHID":"PHID-TASK-he2h6hqmwrdrav3cxqew","transactionPHIDs":{"PHID-XACT-TASK-ix5urhvrpvn22e2":"PHID-XACT-TASK-ix5urhvrpvn22e2"}}},"PHID-STRY-cpcsc3r3444i3vaw66bo":{"class":"PhabricatorApplicationTransactionFeedStory","epoch":1577804267,"authorPHID":"PHID-USER-muirnivxp5hzppn2a3z7","chronologicalKey":"6776617727166200626","data":{"objectPHID":"PHID-TASK-dgq26etiz4wecd24gkmb","transactionPHIDs":{"PHID-XACT-TASK-zd6b2kmmj5pnfwm":"PHID-XACT-TASK-zd6b2kmmj5pnfwm"}}}},"error_code":null,"error_info":null}""")  # noqa


def feed_query_error_response(request, context):
    return json.loads(r"""{"result":null,"error_code":"ERR-CONDUIT-CORE","error_info":"Cursor \"6771969043218032437\" does not identify a valid object in query \"PhabricatorFeedQuery\"."}""")  # noqa


def test_polling(bugs):
    with requests_mock.mock() as m:
        m.post('/api/conduit.connect', json=conduit_connect_1)
        m.post('/api/feed.query', [{'json': feed_query_initial}, {'json': feed_query_second}])
        bugs.poll()
        assert bugs.events == []

        m.post('/api/feed.query', json=feed_query_third)
        bugs.poll()

        assert len(bugs.events) == 3

        # TODO: add more extensive tests


def test_error_response(bugs):
    with requests_mock.mock() as m:
        m.post('/api/conduit.connect', json=conduit_connect_1)
        m.post('/api/feed.query', [{'json': feed_query_initial}, {'json': feed_query_second}])
        bugs.poll()

        m.post('/api/feed.query', json=feed_query_error_response)
        with pytest.raises(phabricator.PhabricatorException):
            bugs.poll()
