from fabric.api import *  # noqa
from fabric.contrib.console import confirm

env.hosts = ['tools-login.wmflabs.org']
env.sudo_user = 'tools.wikibugs'
env.sudo_prefix = 'sudo -ni '

code_dir = '/data/project/wikibugs/wikibugs2'

python = '/data/project/wikibugs/py-wikibugs2/bin/python'
jobs = {
    'wb2-phab': '{python} {code_dir}/wikibugs.py',
    'wb2-irc': '{python} {code_dir}/redis2irc.py',
}


def irclog_deploy(message):
    with cd(code_dir):
        sudo('./log_to_irc.sh "{}"'.format(message))


def pull():
    with cd(code_dir):
        sudo('git reset --hard')
        sudo('git pull')


def start_job(name):
    # string formatting as fab doesn't get list-style commands...
    sudo('jstart -N {name} -l release=trusty -mem 1G -once {command}'.format(
        name=name,
        command=jobs[name].format(**globals())
    ))


def restart_job(name):
    sudo('qmod -rj {name}'.format(name=name))


@task
def start_jobs():
    with settings(warn_only=True):
        start_job('wb2-phab')
        start_job('wb2-irc')


@task
def deploy(*args):
    if len(args) == 0:
        alljobs = list(jobs.keys())
        if not confirm("No jobs provided, assuming {}. OK?".format(', '.join(alljobs)), default=False):
            abort('No jobs provided. Usage: fab deploy:[job]')
            return
        args = alljobs
    pull()
    for job in args:
        restart_job(job)
    irclog_deploy(', '.join(args))
