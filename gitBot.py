# -*- coding: utf-8 -*-
import binascii
import logging
from datetime import datetime
from config import CHATROOM_PRESENCE
from errbot.utils import human_name_for_git_url

POLLING_TIME = 600

from errbot import botcmd, BotPlugin

from git import *
import os
import shutil


class GitBot(BotPlugin):
    min_err_version = '1.7.0'

    def git_poller(self):
        logging.debug('Poll the git repos')
        history_msgs = {}

        for human_name in self:
            initial_state = self[human_name]
            initial_state_dict = dict(initial_state)
            logging.debug('fetch all heads of %s... ' % human_name)
            self.fetch_all_heads(human_name)
            new_state_dict = {head: rev for head, rev in self.get_heads_revisions(human_name)}
            history_msg = ''
            new_stuff = False
            for head in initial_state_dict:
                if initial_state_dict[head] != new_state_dict[head]:
                    logging.debug('%s: %s -> %s' % (head, binascii.hexlify(initial_state_dict[head]), binascii.hexlify(new_state_dict[head])))
                    new_stuff = True

            if new_stuff:
                log = self.git_log(self.history_since_rev(human_name, initial_state))
                for head in log:
                    if log[head]: # don't log the empty branches
                        history_msg += '  Branch ' + head + ':\n    '
                        history_msg += '\n    '.join(log[head]) + '\n'
                history_msgs[human_name] = history_msg
            logging.debug('Saving the shelf')
            self[human_name] = [(head, sha) for head, sha in new_state_dict.items() if head in initial_state_dict]
        if history_msgs:
            if CHATROOM_PRESENCE:
                room = CHATROOM_PRESENCE[0]
                self.send(room, '/me is about to give you the latest git repo news ...', message_type='groupchat')
                for repo, changes in history_msgs.items():
                    msg = ('%s:\n' % repo) + changes
                    logging.debug('Send:\n%s' % msg)
                    self.send(room, msg, message_type='groupchat')

    def activate(self):
        self.start_poller(POLLING_TIME, self.git_poller)
        super(GitBot, self).activate()

    def _git_follow_url(self, git_url, heads_to_follow):
        human_name = human_name_for_git_url(git_url)
        if human_name in self:
            self.fetch_all_heads(human_name)
            current_entry = self[human_name]
        else:
            human_name = self.clone(git_url)
            current_entry = []

        current_entry_dict = dict(current_entry)
        current_entry = [pair for pair in self.get_heads_revisions(human_name) if pair[0] in heads_to_follow or pair[0] in current_entry_dict] if heads_to_follow else self.get_heads_revisions(human_name)
        self[human_name] = current_entry
        return self.git_following(None, None)

    def human_to_path(self, human_name):
        return os.path.join(self.plugin_dir, 'git_repos', human_name)

    def clone(self, url):
        human_name = human_name_for_git_url(url)
        g = Git()
        g.clone(url, self.human_to_path(human_name), bare=True)
        return human_name

    def remove_repo(self, human_name):
        path = self.human_to_path(human_name)
        shutil.rmtree(path)

    def fetch_all_heads(self, human_name):
        path = self.human_to_path(human_name)
        g = Git(path)
        logging.debug('fetch_all_heads from %s' % path)
        remote_heads_string = g.ls_remote('origin', heads=True)
        branches = ['/'.join(line.split('/')[2:]) for line in remote_heads_string.split('\n')]
        repo = Repo(path)
        origin = repo.remotes.origin
        result = []
        for branch in branches:
            logging.debug('fetching = %s' % branch)
            result.extend(origin.fetch('%s:%s' % (branch, branch)))

        logging.debug('result = %s' % result)
        return result

    def get_heads_revisions(self, human_name):
        path = self.human_to_path(human_name)
        repo = Repo(path)
        heads = repo.heads
        return [(h.name, h.commit.binsha) for h in heads]

    def history_since_rev(self, human_name, previous_heads_revisions):
        repo = Repo(self.human_to_path(human_name))
        heads = repo.heads
        result = {}
        for head_name, previous_commit in previous_heads_revisions:
            commit_list = []
            parent_commits = [heads[head_name].commit,]

            while previous_commit not in (commit.binsha for commit in parent_commits):
                new_parents = []
                for commit in parent_commits:
                    commit_list.append(commit)
                    if commit.parents:
                        new_parents.extend(commit.parents)
                parent_commits = new_parents

            result[head_name] = commit_list
        logging.debug('%s, found this history_since_rev %s' % (human_name, result))
        return result

    # Represents a list of commits as a log as a dictionary of list of strings
    def git_log(self, head_commits):
        result = {}
        for head in head_commits:
            commits = head_commits[head]
            logging.debug(u'git log of %s' % head)
            result[head] = [u"%s %20s %20s -- %s" % (commit.hexsha[:6], commit.author.name, datetime.fromtimestamp(commit.committed_date).isoformat(), commit.summary) for commit in commits]
            logging.debug(u'%s' % result[head])
        return result

    @botcmd(split_args_with=' ', admin_only=True)
    def git_follow(self, mess, args):
        """ Follow the given git repository url and be notified when somebody commits something on it
        The first argument is the git url.
        The next optional arguments are the heads to follow.
        If no optional arguments are given, just follow all the heads

        You can alternatively put a name of a plugin or 'allplugins' to follow the changes of the installed r2 plugins.
        """
        if len(args) < 1:
            return 'You need at least a parameter'
        git_name = args[0]
        result = ''
        installed_plugin_repos = self.get_installed_plugin_repos()
        if git_name == 'allplugins':
            for url in [url for _, url in installed_plugin_repos.items()]:
                result = self._git_follow_url(url, None)  # follow everything
            return result
        elif git_name in installed_plugin_repos:
            git_name = installed_plugin_repos[git_name]  # transform the symbolic name to the url

        heads_to_follow = args[1:] if len(args) > 1 else None
        return self._git_follow_url(git_name, heads_to_follow)

    @botcmd(split_args_with=' ', admin_only=True)
    def git_unfollow(self, mess, args):
        """ Unfollow the given git repository url or specific heads
        The first argument is the url.
        The next optional arguments are the heads to unfollow.
        If no optional arguments are given, just unfollow the repo completely
        """
        if len(args) < 1:
            return 'You need a parameter'
        human_name = str(args[0])
        heads_to_unfollow = args[1:] if len(args) > 1 else None

        if human_name not in self:
            return 'I cannot find %s repos' % human_name

        if heads_to_unfollow:
            self[human_name] = [(head, sha) for head, sha in self[human_name] if head not in heads_to_unfollow]
            return 'Heads %s have been removed from %s' % (','.join(heads_to_unfollow), human_name) + '\n\n' + self.git_following(None, None)

        self.remove_repo(human_name)
        del(self[human_name])
        return ('%s has been removed.' % human_name) + '\n\n' + self.git_following(None, None)

    @botcmd
    def git_following(self, mess, args):
        """ Just prints out which git repo the bot is following
        """
        if not self:
            return 'You have no entry, please use !git follow to add some'
        return '\nYou are currently following those repos:\n' + (
            '\n'.join(['\n%s:\n%s' % (human_name, '\t\n'.join([pair[0] for pair in current_entry])) for (human_name, current_entry) in self.items()]))
