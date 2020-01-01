import json
from tests.common import root

import messagebuilder

data_path = root / "tests" / "data" / "messagebuilder"


def test_escaping():
    builder = messagebuilder.IRCMessageBuilder()
    assert builder.escape("bla\nfdafdas") == "bla fdafdas"
    assert builder.escape("bla\r\nfdafdas") == "bla  fdafdas"
    assert builder.escape("Some ```preformatted``` text") == "Some `preformatted` text"
    assert builder.escape("Some `preformatted` text") == "Some `preformatted` text"


def test_formatting():
    useful_info = json.load((data_path / 'backticks').open(encoding='utf-8'))

    useful_info['channel'] = "##wikibugs"
    useful_info['matched_projects'] = ["Operations"]

    builder = messagebuilder.IRCMessageBuilder()
    built = builder.build_message(useful_info)

    expected = "\x0310Operations\x0f, \x0310Traffic\x0f, \x0310Patch-For-Review\x0f: " \
               "Add ex cp-misc_codfw to text and upload - " \
               "https://phabricator.wikimedia.org/T208588 (\x0310ops-monitoring-bot\x0f) " \
               "Script wmf-auto-reimage was launched by ema on sarin.codfw.wmnet for hosts: " \
               "` ['cp2006.codfw.wmnet', 'cp2012.codfw.wmnet'] ` The log can be found in `/var/lo..."

    assert built == expected
