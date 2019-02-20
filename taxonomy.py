from collections import OrderedDict
import phabricator
import configfetcher
import pywikibot

conf = configfetcher.ConfigFetcher()

# Fetch projects
phab = phabricator.Phabricator(
    conf.get('PHAB_HOST'),
    conf.get('PHAB_USER'),
    conf.get('PHAB_CERT')
)

# note: Pywikibot config is loaded from ~/.pywikibot

projects = []

offset = 0
step = 1000

for i in range(1000):
    result = phab.request('project.query', {'limit': step, 'offset': offset})['data']
    if len(result) == 0:
        break
    projects.extend(result.values())
    offset += len(result)
else:
    raise Exception('Took more than 1000 request; aborting')


# Build taxanomy
projecttypes = OrderedDict([
    ('project', 'Projects'),
    ('group', 'User groups'),
    ('tag', 'Tags'),
    ('umbrella', 'Umbrella projects'),
    ('account', 'User projects'),
    ('goal', 'Goals'),
    ('milestone', 'Milestones'),
    ('release', 'Releases'),
    ('timeline', 'Sprints'),
])

for icon in sorted(set((x['icon']) for x in projects)):
    if icon not in projecttypes:
        projecttypes[icon] = icon + " (unknown)"

wikipage = "{{/Header}}\n"

for icon, header in projecttypes.items():
    wikipage += "=== {} ===\n".format(header)
    projects_f = sorted(
        (project for project in projects if
            project['icon'] == icon and
            project['color'] != 'disabled'),
        key=lambda p: p['name'].strip('§ ')
    )

    for project in projects_f:
        name = project['name']
        id = project['id']

        if '-' not in name:
            superproject = name
            wikipage += "* "
        else:
            if superproject not in name:
                superproject = name.split("-")[0]
                wikipage += "* {}\n".format(superproject)
            wikipage += "** "
        wikipage += "[[phab:project/view/{}/|{}]]\n".format(
            project['id'], project['name']
        )

wikipage += "\n{{/Footer}}"


# Save to page on-wiki
site = pywikibot.Site(fam='mediawiki', code='mediawiki')
page = pywikibot.Page(site, 'Phabricator/Projects')
page.text = wikipage
page.save(comment='Updating project taxonomy', botflag=False)
