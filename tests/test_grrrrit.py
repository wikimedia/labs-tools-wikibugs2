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


def test_new_patchset_created():
    events = json.load((data_path / "new_patchset_created.json").open())
    processed = process_events(events)

    assert processed[0] == {
        'type': 'PS1',
        'user': 'UserName',
        'message': 'test',
        'branch': 'master',
        'repo': 'test',
        'task': None,
        'url': 'https://gerrit.git.wmflabs.org/r/2001'}
