import json
import queue

import pytest
import requests_mock

import configfetcher
import wikibugs
from tests.common import root
from tests.wikibugs_network.common import parse_request, conduit_connect, unexpected

data_path = root / "tests" / "wikibugs_network" / "data"


class WikibugsFixture:
    def __init__(self):
        self.errors = []
        self.wikibugs = wikibugs.Wikibugs2(
            configfetcher.ConfigFetcher(str(root / "config.json.example"))
        )
        self.queue = self.wikibugs.rqueue = queue.Queue()
        self.wikibugs.dump_error = lambda *args: self.errors.append(args)

    def process_event(self, event):
        self.wikibugs.process_event(event)


@pytest.fixture()
def bugs():
    return WikibugsFixture()


def phid_query_1(request, context):
    content = parse_request(request)
    assert content["phids"] == ["PHID-TASK-bc37zzm5ct4wi2ill4xq"]
    return json.loads(r"""{"result":{"PHID-TASK-bc37zzm5ct4wi2ill4xq":{"phid":"PHID-TASK-bc37zzm5ct4wi2ill4xq","uri":"https:\/\/phabricator.wikimedia.org\/T241635","typeName":"Task","type":"TASK","name":"T241635","fullName":"T241635: Request creation of commons-corruption-checker VPS project","status":"open"}},"error_code":null,"error_info":null}""")  # noqa


def maniphest_info_1(request, context):
    content = parse_request(request)
    assert content["task_id"] == 241635
    return json.loads(r"""{"result":{"id":"241635","phid":"PHID-TASK-bc37zzm5ct4wi2ill4xq","authorPHID":"PHID-USER-vjmtjihjwrw3oh3mhwzs","ownerPHID":null,"ccPHIDs":["PHID-USER-uxkuzijnonyzorsbopou","PHID-USER-g7ljr7obhy5hgp4qpuiw","PHID-USER-hwuumsjqciw7ji5qhpc7","PHID-USER-hgn5uw2jafgjgfvxibhh","PHID-USER-vjmtjihjwrw3oh3mhwzs","PHID-USER-53x4y44yt43qjivfzsqf"],"status":"open","statusName":"Open","isClosed":false,"priority":"Needs Triage","priorityColor":"violet","title":"Request creation of commons-corruption-checker VPS project","description":"**Project Name:** commons-corruption-checker\n\n**Wikitech Usernames of requestors:** TheSandDoctor\n\n**Purpose:** Check existing images on Wikimedia Commons for corruption and monitor uploads indefinitely\n\n**Brief description:** This task will require the installation of python and python packages: mwclient, mwparserfromhell, Pywikibot, sseclient, and my own [[ https:\/\/github.com\/TheSandDoctor\/Pillow | version ]] of [[https:\/\/github.com\/Pillow\/Pillow | Pillow ]] (PIL). I need this version to be installed due to the potential for large images. This bot task has been [[ https:\/\/commons.wikimedia.org\/wiki\/Commons:Bots\/Requests\/TheSandBot_2 | approved on Commons]]. This task works by downloading all of the images (though only one at a time will be processed\/downloaded and deleted afterwords), scanning them, and then logging in a database the result. In the event that corruption is detected, the uploader is then notified. After either 7 (for new uploads) or 30 days (existing catalogue) has passed, the images are then re-downloaded and re-checked. If their hashes match the previously checked version (aka unchanged\/still corrupt), then it is tagged for speedy deletion and the uploader notified of this action.\n\nI am definitely open to adding collaborators on this task\/project and would not have \"closed\" membership.\n\n**How soon you are hoping this can be fulfilled:**  as soon as possible (e.g. January some time if possible?)","projectPHIDs":["PHID-PROJ-ttxr7uvf6v5zi2k3gg36"],"uri":"https:\/\/phabricator.wikimedia.org\/T241635","auxiliary":{"std:maniphest:deadline.due":null,"std:maniphest:release.version":null,"std:maniphest:release.date":null,"std:maniphest:security_topic":"default","std:maniphest:train.backup":null,"std:maniphest:risk.summary":null,"std:maniphest:risk.impacted":null,"std:maniphest:risk.rating":null,"std:maniphest:error.reqid":null,"std:maniphest:error.stack":null,"std:maniphest:error.url":null,"std:maniphest:error.id":null,"std:maniphest:points.final":null},"objectName":"T241635","dateCreated":"1577770778","dateModified":"1577851480","dependsOnTaskPHIDs":[]},"error_code":null,"error_info":null}""")  # noqa


def T241635(request, context):
    return (data_path / "T241635").open().read()


def user_query_1(request, context):
    content = parse_request(request)
    assert content['phids'] == ['PHID-USER-g7ljr7obhy5hgp4qpuiw']
    return json.loads(r"""{"result":[{"phid":"PHID-USER-g7ljr7obhy5hgp4qpuiw","userName":"UserName","realName":"RealName","image":"https:\/\/phab.wmfusercontent.org\/file\/data\/pdvgf6bwbegtkliymkn2\/PHID-FILE-xratrbg4u35mp2lcxckv\/profile","uri":"https:\/\/phabricator.wikimedia.org\/p\/UserName\/","roles":["verified","approved","activated"]}],"error_code":null,"error_info":null}""")  # noqa


def test_events(bugs):
    with requests_mock.mock() as m:
        m.post('/api/conduit.connect', [{'json': conduit_connect}, {'json': unexpected}])
        m.post('/api/phid.query', [{'json': phid_query_1}, {'json': unexpected}])
        m.post('/api/maniphest.info', [{'json': maniphest_info_1}, {'json': unexpected}])
        m.get('/T241635', [{'text': T241635}, {'text': unexpected}])
        m.post('/api/user.query', [{'json': user_query_1}, {'json': unexpected}])
        event = json.loads(r"""{"class": "PhabricatorTokenGivenFeedStory", "epoch": 1577833604, "authorPHID": "PHID-USER-g7ljr7obhy5hgp4qpuiw", "chronologicalKey": "6776743729549210107", "data": {"authorPHID": "PHID-USER-g7ljr7obhy5hgp4qpuiw", "tokenPHID": "PHID-TOKN-misc-1", "objectPHID": "PHID-TASK-bc37zzm5ct4wi2ill4xq"}}""")  # noqa
        bugs.process_event(event)

        assert len(bugs.errors) == 1
        t, exc, ev = bugs.errors[0]
        assert t == "XACT-anchor"
        assert ev == event

        assert bugs.queue.empty()
