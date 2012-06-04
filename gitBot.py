# -*- coding: utf-8 -*-
from botplugin import BotPlugin
from jabberbot import botcmd
from gittools import clone, pull, get_heads_revisions
from utils import human_name_for_git_url

class GitBot(BotPlugin):
    @botcmd
    def follow(self, mess, args):
        """ Follow the given git repository url and be notified when somebody commits something on it
        The first argument is the url.
        The next optional arguments are the heads to follow.
        If no optional arguments are given, just follow all the heads
        """
        args = args.strip().split(' ')
        if len(args) < 1:
            return 'You need at least a parameter'
        git_url = args[0]
        heads_to_follow = args[1:] if len(args)>1 else None

        human_name = human_name_for_git_url(git_url)

        if self.shelf.has_key(human_name):
            pull(human_name)
            current_entry = self.shelf[human_name]
        else:
            clone(human_name)
            current_entry = []

        current_entry_dict = dict(current_entry)
        current_entry = [pair for pair in get_heads_revisions(human_name) if pair[0] in heads_to_follow or pair[0] in current_entry_dict] if heads_to_follow else get_heads_revisions(human_name)
        self.shelf[human_name] = current_entry
        self.shelf.sync()

        return '\n%s:\n%s' % (human_name, '\t\n'.join([pair[0] for pair in current_entry]))


    @botcmd
    def unfollow(self, mess, args):
        """ Unfollow the given git repository url or specific heads
        The first argument is the url.
        The next optional arguments are the heads to unfollow.
        If no optional arguments are given, just unfollow the repo completely
        """
        return 'ok'


    @botcmd
    def following(self, mess, args):
        """ Just prints out which git repo the bot is following
        """
        return 'ok'
