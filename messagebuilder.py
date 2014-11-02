#!/usr/bin/env python


class IRCMessageBuilder(object):
    MAX_MESSAGE_LENGTH = 80*4

    COLORS = {'white': 0, 'black': 1, 'blue': 2, 'green': 3, 'red': 4, 'brown': 5,
              'purple': 6, 'orange': 7, 'yellow': 8, 'lime': 9, 'teal': 10,
              'cyan': 11, 'royal': 12, 'pink': 13, 'grey': 14, 'silver': 15}

    def colorify(self, text, foreground=None, background=None):
        outtext = "\x03"
        if foreground:
            outtext += str(self.COLORS[foreground])
        if background:
            outtext += "," + str(self.COLORS[background])
        outtext += text
        outtext += "\x03"

        return outtext

    def build_message(self, useful_info):
        text = ''
        if useful_info['projects']:
            text += self.colorify(', '.join(useful_info['projects']), 'green')
            text += ': '
        text += useful_info['title']
        text += ' - ' + useful_info['url']
        text += " (" + self.colorify(useful_info['user'], "teal") + ") "
        return text
