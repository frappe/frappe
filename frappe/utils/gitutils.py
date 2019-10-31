from __future__ import unicode_literals
import re

import subprocess

def get_app_branch(app):
	'''Returns branch of an app'''
	try:
		branch = subprocess.check_output('cd ../apps/{0} && git rev-parse --abbrev-ref HEAD'.format(app),
			shell=True)
		branch = branch.decode('utf-8')
		branch = branch.strip()
		return branch
	except Exception:
		return ''

def get_app_last_commit_ref(app):
	try:
		commit_id = subprocess.check_output('cd ../apps/{0} && git rev-parse HEAD'.format(app),
			shell=True)
		commit_id = commit_id.decode('utf-8')
		commit_id = commit_id.strip()[:7]
		return commit_id
	except Exception:
		return ''

def get_revision(app, commit="HEAD"):
	print("Getting revision for {}".format(commit))
	try:
		command = 'cd ../apps/{0} && git rev-list '.format(app) + commit +' --count'
		rev = subprocess.check_output(command, shell=True)
		rev = rev.decode('utf-8')
		rev = rev.strip()
		return rev
	except Exception:
		return ''

def get_changelog(app):
    try:
        command = " && ".join(['cd ../apps/{0}'.format(app),
                               'git log -10 --pretty="format:dkwkkwToken__: %<(11,trunc)%H %cd:dkwkkwEnd%B"'])
        rev = subprocess.check_output(command, shell=True)
        rev = rev.decode('utf-8')
        rev = rev.strip()
        retVal = []
        commits = rev.split("dkwkkwToken__: ")[1:]
        # commits = re.findall(r"(dkwkkwToken__: (.*? ))", rev)
        for c in commits:
            cHash = re.search("(.{9})", c)
            if cHash is not None:
                    cHash = cHash.group(1)
                    revision = get_revision(app, cHash)
                    newC = c.replace(cHash + "..", "rev:" + revision + "/" + cHash + " ")
                    retVal.append(newC.split("dkwkkwEnd"))
        return retVal
    except Exception:
        return ''


