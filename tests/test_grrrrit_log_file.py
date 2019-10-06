# Process events from a grrrrit.log log file. For privacy reasons, the log files are not included in
# the repository. To use this test, simply grab a a log file and place it in the data directory.

from pathlib import Path
import json
import pytest
import grrrrit

root = Path(__file__).parent.parent
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
        if " - INFO - {" not in line:
            continue

        try:
            line = line.split("- INFO - ")[1]
            line = json.loads(line)
        except Exception as e:
            print(i, line, e)
            raise

        if "eventCreatedOn" in line:
            # heuristic: this is a gerrit logged event
            processed_event = grrrrit.process_event(line)
            if processed_event:
                if current_expectation is not None:
                    diff.append(("+", current_expectation_line, current_expectation))

                current_expectation = processed_event
                current_expectation_line = i
        else:
            if current_expectation != line:
                diff.append(("-", i, line))
            else:
                current_expectation = None
                current_expectation_line = -1

    for l in diff:
        print("{1}: {0}  {2}".format(*l))

    assert len(diff) == 0
