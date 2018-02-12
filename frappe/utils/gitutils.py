from __future__ import unicode_literals

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
