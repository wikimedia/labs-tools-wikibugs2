import grrrrit


def verify(project, branch, channels, *, not_in=set()):
    """Verifies the change is reported to _at least_ the channels passed *and* the firehose channel,
    and _not_ in not_channels

    This limits the effects of additional reporting channels added to the yaml file on the tests."""

    firehose_channel = "#mediawiki-feed"

    report_channels = grrrrit.channel_filter(project, branch)
    assert report_channels >= (channels | {firehose_channel})
    assert (report_channels & not_in) == set()


def test_pywikibot_channels():
    verify("pywikibot/core", "master", {"#pywikibot"})
    verify("pywikibot/core", "refs/meta/config", {"#pywikibot", "#wikimedia-releng"})


def test_betacluster():
    verify("operations/puppet", "master", {"#wikimedia-operations"})
    verify("operations/puppet", "betacluster", {"#wikimedia-releng"}, not_in={"#wikimedia-operations"})

    verify("operations/debs/wikistats", "master", set(), not_in={"#wikimedia-operations"})
    verify("operations/debs/wikistats", "betacluster", {"#wikimedia-releng"}, not_in={"#wikimedia-operations"})


def test_default():
    verify("non_registered_project", "master", {"#wikimedia-dev"})

    # TODO: are this intended/expected?
    verify("non_registered_project", "refs/meta/config", {"#wikimedia-releng"}, not_in={"wikimedia_dev"})
    verify("non_registered_project", "wmf/test", {"#wikimedia-operations"}, not_in={"wikimedia_dev"})


def test_mw_core():
    verify("mediawiki/core", "master", {"#wikimedia-dev"})
    verify("mediawiki/core", "fundraising", {"#wikimedia-dev", "#wikimedia-fundraising"})
    verify("mediawiki/core", "fundraising/test", {"#wikimedia-dev", "#wikimedia-fundraising"})
    verify("mediawiki/core", "refs/meta/config", {"#wikimedia-dev", "#wikimedia-releng"})
    verify("mediawiki/core", "wmf/1.34.0-wmf.16", {"#wikimedia-dev", "#wikimedia-operations"})


def test_mw_extension():
    # TODO: is it expected that this extension is not reported in #wikimedia-dev?
    proj = "mediawiki/extensions/CentralNotice"

    verify(proj, "master", {"#wikimedia-fundraising"}, not_in={"#wikimedia-dev"})
    verify(proj, "refs/meta/config", {"#wikimedia-fundraising", "#wikimedia-releng"}, not_in={"#wikimedia-dev"})
    verify(proj, "wmf/1.34.0-wmf.16", {"#wikimedia-fundraising", "#wikimedia-operations"}, not_in={"#wikimedia-dev"})
