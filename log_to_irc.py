#!/usr/bin/env python
import sys
import os
import subprocess
import json

config_file = os.path.join(
    os.path.dirname(__file__),
    'config.json'
)
config = json.load(open(config_file))

token = config['IRCNOTIFIER_KEY']
message = '!log {user} {sudo_user}: Deployed {rev} {msg}'.format(
    user=os.environ['USER'],
    sudo_user=os.environ['SUDO_USER'],
    rev=subprocess.check_output(["git", "rev-list", "HEAD",
                                 "--max-count=1", "--format=oneline"]
                                ).decode('utf-8').strip(),
    msg=' '.join(sys.argv[1:])
)

print(message)
