import shlex
import sys

import click
import socket
import subprocess

tool_name = 'wikibugs'

home_dir = '/data/project/{}'.format(tool_name)
code_dir = '{}/libera'.format(home_dir)
python = '{}/py35-stretch/bin/python'.format(home_dir)

job_definitions = {
    'libera-phab': [python, code_dir + '/wikibugs.py', '--logfile', home_dir + '/wikibugs.log'],
    'libera-irc': [python, code_dir + '/redis2irc.py', '--logfile', home_dir + '/redis2irc.log'],
    'libera-grrrrit': [python, code_dir + '/grrrrit.py', '--logfile', home_dir + '/grrrrit.log'],
}

jsub = '/usr/bin/jsub'
jsub_params = [
    '-mem', '1G',
    '-once',
    '-v', 'PYTHONIOENCODING="utf8:backslashreplace"'
]


class RealRun:
    def run(self, wd, command, fail_ok=False):
        print(wd + '$ ' + ' '.join(shlex.quote(x) for x in command))

        if fail_ok:
            subprocess.call(command, cwd=wd)
        else:
            subprocess.check_call(command, cwd=wd)


class MockRun:
    cwd = home_dir

    def run(self, wd, command, fail_ok=False):
        if wd is not None and wd != self.cwd:
            print()
            print("cd " + shlex.quote(wd))
            self.cwd = wd
        print(' '.join(shlex.quote(x) for x in command))


def check_job(name):
    if name not in job_definitions:
        raise ValueError("Unknown job {name}, expected one of {jobs}".format(
            name=name, jobs=', '.join(job_definitions)))


@click.group()
@click.option('--dry-run/--no-dry-run', default=False, help='do not execute commands')
def cli(dry_run):
    if not socket.getfqdn().endswith('tools.eqiad.wmflabs') and not dry_run:
        print('Running on a non-tools host; cannot execute commands.')
        print('To show expected commands, pass --dry-run')
        print('To execute the commands, ssh into the tool and run the script there, or run:')
        print('ssh tools-login.wmflabs.org sudo -niu tools.{toolname} {python} {code_dir}/manage.py {args}'.format(
            toolname=tool_name, python=python, code_dir=code_dir, args=' '.join(shlex.quote(x) for x in sys.argv[1:]))
        )

        raise click.Abort()

    global R
    R = MockRun() if dry_run else RealRun()


@cli.command()
def pull():
    R.run(code_dir, ['git', 'rev-list', 'HEAD', '--max-count=1'])
    R.run(code_dir, ['git', 'reset', '--hard', 'origin/master'])
    R.run(code_dir, ['git', 'pull'])


@cli.command()
@click.argument('job')
def start_job(job):
    check_job(job)
    R.run(home_dir, [jsub, '-N', job] + jsub_params + ['-continuous'] + job_definitions[job], fail_ok=True)


@cli.command()
@click.pass_context
def start_jobs(ctx):
    for job in job_definitions:
        ctx.invoke(start_job, job=job)


@cli.command()
@click.argument('job')
def restart_job(job):
    check_job(job)
    R.run(home_dir, ['qmod', '-rj', job], fail_ok=True)


@cli.command()
@click.argument('jobs', nargs=-1)
@click.pass_context
def deploy(ctx, jobs):
    if len(jobs) == 0:
        jobs = list(job_definitions.keys())
        click.confirm(
            "No jobs provided, assuming {}. OK?".format(', '.join(jobs)),
            abort=True
        )

    ctx.invoke(pull)
    for job in jobs:
        ctx.invoke(restart_job, job=job)


if __name__ == "__main__":
    cli()
