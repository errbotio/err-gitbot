from git import *
from errBot import PLUGIN_DIR
from utils import human_name_for_git_url
import os
GIT_LOCAL_STORAGE = PLUGIN_DIR + os.sep + 'git_repos' + os.sep
g = Git()

def human_to_path(human_name):
    return GIT_LOCAL_STORAGE + human_name

def clone(url):
    human_name = human_name_for_git_url(url)
    g.clone(url, human_to_path(human_name), bare=True)
    return human_name

def pull(human_name):
    g.pull(human_to_path(human_name))

def get_heads_revisions(human_name):
    path = human_to_path(human_name)
    repo = Repo(path)
    heads = repo.heads
    return [(h.name, h.commit.binsha) for h in heads]

def history_since_rev(path, previous_heads_revisions):
    repo = Repo(path)
    heads = repo.heads
    for head_name, previous_commit in previous_heads_revisions:
        head = heads[head_name]
        log = head.log()
        log.reverse()
        for commit in log:
            if commit.newhexsha == previous_commit:
                break
            print head_name, commit
