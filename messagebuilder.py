#!/usr/bin/env python


class IRCMessageBuilder(object):
    MAX_MESSAGE_LENGTH = 80 * 4
    MAX_NUM_PROJECTS = 4

    COLORS = {
        'white': 0, 'black': 1, 'blue': 2, 'green': 3, 'red': 4, 'brown': 5,
        'purple': 6, 'orange': 7, 'yellow': 8, 'lime': 9, 'teal': 10,
        'cyan': 11, 'royal': 12, 'pink': 13, 'grey': 14, 'silver': 15,
    }

    # The following colors are safe for use on both black and white backgrounds:
    # green, red, brown, purple, orange, teal, cyan, royal, pink, grey, silver
    #
    # Make sure to define a background when using other colors!

    PHAB_COLORS = {
        # Matches phabricator project colors to IRC colors
        'blue': 'teal',
        'red': 'brown',
        'orange': 'brown',
        'yellow': 'orange',
        'indigo': 'royal',
        'violet': 'purple',
        'green': 'green',
        'grey': 'grey',
        'pink': 'pink',
        'checkered': 'silver',
    }

    PRIORITY = {
        '100': 'Unbreak!',
        '90': 'Triage',
        '80': 'High',
        '50': 'Normal',
        '25': 'Low',
        '10': 'Volunteer?',
    }

    # FIXME: Incomplete
    STATUSES = {
        'open': 'Open',
        'needsinfo': 'Needs info',
        'invalid': 'Invalid',
        'resolved': 'Resolved',
    }

    OUTPUT_PROJECT_TYPES = ['briefcase', 'users', 'umbrella']

    # Style may be stripped by irc3 if it's a the beginning (or end) of a line
    TEXT_STYLE = {
        'bold': '\x02',
        'underline': '\x1f',
        'reversed': '\x16',
    }

    def ircformat(self, text, foreground=None, background=None, style=None):
        outtext = ""
        if foreground or background:
            outtext += "\x03"
        if foreground:
            outtext += str(self.COLORS[foreground])
        if background:
            outtext += "," + str(self.COLORS[background])
        if style:
            outtext += self.TEXT_STYLE[style]
        outtext += text
        if foreground or background or style:
            outtext += "\x0f"
        return outtext

    def _human_status(self, name):
        return self.STATUSES.get(name, name)

    def _human_prio(self, name):
        return self.PRIORITY.get(str(name), str(name))

    def escape(self, text):
        """
        Escape user supplied text so it can't be abused to
        execute arbitrary IRC commands
        :param text: possibly unsafe input
        :return: safe output
        """
        return text.replace('\n', ' ').replace('\r', ' ')

    def build_project_text(self, all_projects, matched_projects):
        """
        Build project text to be shown.
        Requirement:
            (1) Show matched projects first, and bold
            (2) Next, show other projects if they are in self.OUTPUT_PROJECT_TYPES
            (3) Then other tags
            (4) But never show disabled text
            (5) Unless there aren't any tags at all otherwise
            (6) If there are no projects at all, show "(no projects)" in bright red
            (7) Never show more than self.MAX_NUM_PROJECTS, even if they are matched

        :param all_projects: dict[project name, info] (scraped) or
                             list[project name] (failed scraping)
        :param matched_projects: list[project name]
        :return: list with formatted projects
        """

        # (3) format all projects
        # and map to a standardized format in the process
        projects = {}
        for project in all_projects:
            try:
                info = all_projects[project]
            except KeyError:
                info = {
                    'shade': 'green',
                    'tagtype': 'briefcase',
                    'disabled': False,
                    'uri': ''
                }
            info['matched'] = project in matched_projects

            color = self.PHAB_COLORS.get(info['shade'], 'teal')
            info['irc_text'] = self.ircformat(project, color)

            projects[project] = info

        # We map projects in four categories:
        matched_parts = []
        other_projects = []
        other_tags = []
        hidden_parts = []

        # We use them in that order, limiting to N (or (N-1) + 'and M others') projects
        for project in sorted(projects):
            info = projects[project]
            if info['matched']:
                matched_parts.append(info['irc_text'])
            elif info['disabled']:
                hidden_parts.append(info['irc_text'])
            elif info['tagtype'] in self.OUTPUT_PROJECT_TYPES:
                other_projects.append(info['irc_text'])
            else:
                other_tags.append(info['irc_text'])

        # (1), (2), (3), (4)
        show_parts = matched_parts + other_projects + other_tags

        # (5), (6)
        if len(show_parts) == 0:
            show_parts = hidden_parts
        if len(show_parts) == 0:
            show_parts = [self.ircformat('(no projects)', 'red', style='bold')]

        # (7)
        overflow_parts = show_parts[self.MAX_NUM_PROJECTS:]
        show_parts = show_parts[:self.MAX_NUM_PROJECTS]

        if len(overflow_parts) == 1:
            show_parts.append(overflow_parts[0])
        elif len(overflow_parts) > 0:
            show_parts.append("and %i others" % len(overflow_parts))
        return ", ".join(show_parts)

    def build_message(self, useful_info):
        text = self.build_project_text(useful_info['projects'], useful_info['matched_projects']) + ': '
        text += useful_info['title']
        text += ' - ' + useful_info['url']
        text += " (" + self.ircformat(useful_info['user'], "teal") + ") "
        is_new = 'new' in useful_info
        if is_new:
            text += self.ircformat('NEW', 'green') + ' '
        elif 'status' in useful_info:
            status = useful_info['status']
            text += self.ircformat(self._human_status(status['old']), 'brown')
            text += '>'
            text += self.ircformat(self._human_status(status['new']), 'green') + ' '
        if 'priority' in useful_info:
            prio = useful_info['priority']
            text += 'p:'
            if prio['old']:
                text += self.ircformat(self._human_prio(prio['old']), 'brown')
                text += '>'
            text += self.ircformat(self._human_prio(prio['new']), 'green')
            text += ' '
        if 'assignee' in useful_info:
            ass = useful_info['assignee']
            text += 'a:'
            if ass['old']:
                text += self.ircformat(ass['old'], 'brown')
                text += '>'
            text += self.ircformat(str(ass['new']), 'green')
            text += ' '

        if 'comment' in useful_info:
            text += useful_info['comment']

        # Get rid of annoying stuff
        text = self.escape(text)
        text = text.replace('\t', ' ')
        if len(text) > self.MAX_MESSAGE_LENGTH:
            text = text[:self.MAX_MESSAGE_LENGTH-3].rstrip() + "..."

        # Make sure the URL is always fully present
        if useful_info['url'] not in text:
            inserttext = "... - " + useful_info['url']
            text = text[:-len(inserttext)] + inserttext

        return text
