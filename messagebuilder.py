#!/usr/bin/env python


class IRCMessageBuilder(object):
    MAX_MESSAGE_LENGTH = 80 * 4

    COLORS = {'white': 0, 'black': 1, 'blue': 2, 'green': 3, 'red': 4, 'brown': 5,
              'purple': 6, 'orange': 7, 'yellow': 8, 'lime': 9, 'teal': 10,
              'cyan': 11, 'royal': 12, 'pink': 13, 'grey': 14, 'silver': 15}

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

    def colorify(self, text, foreground=None, background=None):
        outtext = "\x03"
        if foreground:
            outtext += str(self.COLORS[foreground])
        if background:
            outtext += "," + str(self.COLORS[background])
        outtext += text
        outtext += "\x03"

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

    def build_message(self, useful_info):
        text = ''
        if useful_info['projects']:
            # This could be either a dict (if we are able to scrape all the info)
            # Or a list, if it could not scrape all the info. Handle both cases.
            if isinstance(useful_info['projects'], dict):
                visible_projects = [
                    p for p, info in useful_info['projects'].items()
                    if info['tagtype'] in self.OUTPUT_PROJECT_TYPES and not info['disabled']]
            else:
                visible_projects = useful_info['projects']
            text += self.colorify(', '.join(visible_projects), 'green')
            text += ': '
        text += useful_info['title']
        text += ' - ' + useful_info['url']
        text += " (" + self.colorify(useful_info['user'], "teal") + ") "
        is_new = 'new' in useful_info
        if is_new:
            text += self.colorify('NEW', 'green') + ' '
        elif 'status' in useful_info:
            status = useful_info['status']
            text += self.colorify(self._human_status(status['old']), 'brown')
            text += '>'
            text += self.colorify(self._human_status(status['new']), 'green') + ' '
        if 'priority' in useful_info:
            prio = useful_info['priority']
            text += 'p:'
            if prio['old']:
                text += self.colorify(self._human_prio(prio['old']), 'brown')
                text += '>'
            text += self.colorify(self._human_prio(prio['new']), 'green')
            text += ' '
        if 'assignee' in useful_info:
            ass = useful_info['assignee']
            text += 'a:'
            if ass['old']:
                text += self.colorify(ass['old'], 'brown')
                text += '>'
            text += self.colorify(str(ass['new']), 'green')
            text += ' '

        if 'comment' in useful_info:
            text += useful_info['comment']

        # Get rid of annoying stuff
        text = self.escape(text)
        text = text.replace('\t', ' ')
        if len(text) > self.MAX_MESSAGE_LENGTH:
            text = text[:self.MAX_MESSAGE_LENGTH-3].strip() + "..."

        return text
