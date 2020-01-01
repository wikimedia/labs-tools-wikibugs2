import json
import urllib.parse
from collections import OrderedDict


def parse_request(request):
    decoded = OrderedDict(urllib.parse.parse_qsl(request.text))
    assert decoded['output'] == 'json'
    return json.loads(decoded['params'])


def conduit_connect(request, context):
    return {'result': {'sessionKey': 'key', 'connectionID': 1}}


def unexpected(request, context):
    raise Exception("Received unexpected request: " + request)
