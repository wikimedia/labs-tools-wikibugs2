#!/usr/bin/env bash
echo '#wikimedia-labs !log' $USER $SUDO_USER: Deployed `git rev-list HEAD --max-count=1 --format=oneline` "$@" | nc wm-bot.eqiad.wmflabs 64834 -w0
