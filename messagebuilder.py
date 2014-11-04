#!/usr/bin/env python


class IRCMessageBuilder(object):
    MAX_MESSAGE_LENGTH = 80 * 4

    COLORS = {'white': 0, 'black': 1, 'blue': 2, 'green': 3, 'red': 4, 'brown': 5,
              'purple': 6, 'orange': 7, 'yellow': 8, 'lime': 9, 'teal': 10,
              'cyan': 11, 'royal': 12, 'pink': 13, 'grey': 14, 'silver': 15}

    # TODO FIXME I cannot figure these out at all.
    PRIORITY = {
        '100': 'Unbreak now!',
        '90': 'High',
        '80': 'Low',
        '25': 'Needs volunteer',
    }

    # FIXME: Incomplete
    STATUSES = {
        'open': 'Open',
        'needsinfo': 'Needs info',
        'invalid': 'Invalid',
    }

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

    def build_message(self, useful_info):
        text = ''
        if useful_info['projects']:
            text += self.colorify(', '.join(useful_info['projects']), 'green')
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

        if 'comment' in useful_info:
            text += ' '.join(useful_info['comment'].split('\n'))
            pass

        # Get rid of annoying stuff
        text = text.replace('\t', ' ')
        if len(text) > self.MAX_MESSAGE_LENGTH:
            text = text[:self.MAX_MESSAGE_LENGTH-3].strip() + "..."

        return text
