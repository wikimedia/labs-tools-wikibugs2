# Process events from a grrrrit.log log file. For privacy reasons, the log files are not included in
# the repository. To use this test, simply grab a a log file and place it in the data directory.

from pathlib import Path
import json
import pytest
import grrrrit
from tests.common import root

data_path = root / "tests" / "data"


@pytest.mark.skip
def test_no_changes():
    gerrit_log_files = list(data_path.glob("grrrrit.log*"))
    assert len(gerrit_log_files) > 0, "Expected at least one grrrit.log* file in the data folder"

    for logfile in gerrit_log_files:
        process_log_file(logfile)


def process_log_file(logfile: Path):
    current_expectation = None
    current_expectation_line = -1
    diff = []

    for i, line in enumerate(logfile.open(encoding='utf-8')):
        if 'stream-events: ' in line:
            line = line.split("stream-events: ")[1].strip()
            if line == 'Connection to gerrit.wikimedia.org closed by remote host.':
                continue
            line = json.loads(line)

            processed_event = grrrrit.process_event(line)
            if processed_event:
                if current_expectation is not None:
                    diff.append(("+", current_expectation_line, current_expectation))

                current_expectation = processed_event
                current_expectation_line = i
        elif 'processed: ' in line:
            line = line.split('processed: ')[1]
            line = json.loads(line.strip())

            if current_expectation != line:
                diff.append(("-", i, line))
            else:
                current_expectation = None
                current_expectation_line = -1

    for diffline in diff:
        print("{1}: {0}  {2}".format(*diffline))

    assert len(diff) == 0
