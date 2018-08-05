import json
from collections import OrderedDict
from pathlib import Path

replace = {
    'name': 'RealName {}',
    'email': 'email.{}@example.com',
    'username': 'UserName {}'
}


def recursive_replace(key, value, replacements_used):
    if key in replace:
        if value not in replacements_used[key]:
            replacements_used[key][value] = replace[key].format(len(replacements_used[key]))
        return replacements_used[key][value]

    if isinstance(value, list):
        return [recursive_replace(None, x, replacements_used) for x in value]

    if isinstance(value, dict):
        return OrderedDict(
            (k, recursive_replace(k, v, replacements_used)) for (k, v) in value.items()
        )

    return value


for f in Path(__file__).parent.glob("*.json"):
    print(f)
    parsed = json.load(f.open(), object_pairs_hook=OrderedDict)

    replacements_used = {
        'name': {'jenkins-bot': 'jenkins-bot'},
        'email': {'no-jenkins-bot-email': 'no-jenkins-bot-email'},
        'username': {'jenkins-bot': 'jenkins-bot'}
    }

    f.open('w').write(json.dumps(recursive_replace(None, parsed, replacements_used), indent=2))
