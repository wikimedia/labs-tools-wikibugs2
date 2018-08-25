from pathlib import Path

import click
import subprocess

basepath = Path(__file__).parent.parent.resolve()


def listify(users):
    return "\n".join("- " + u for u in sorted(users, key=str.lower))


def get_all_authors():
    commit_log_authors = subprocess.check_output(['git', 'log', '--format=%an']).decode('utf-8')
    return set(x.strip() for x in commit_log_authors.split("\n") if x.strip() != "")


@click.command()
def update_contributors():
    maintainers = {"Kunal Mehta", "YuviPanda", "Merlijn van Deen"}
    duplicates = {"Legoktm", "Adam Wight", "Florian", "jenkins-bot", "quiddity-wp"}

    contributors = (get_all_authors() - maintainers - duplicates)
    marked_maintainers = {m + " (maintainer)" for m in maintainers}

    with (basepath / 'CREDITS').open('w', encoding='utf-8') as f:
        f.write("We would like to thank all of our contributors for helping improve wikibugs!\n")
        f.write("\n")
        f.write(listify(contributors | marked_maintainers))
        f.write("\n")


if __name__ == "__main__":
    update_contributors()
