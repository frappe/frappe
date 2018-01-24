from __future__ import unicode_literals

import subprocess

def get_app_branch(app):
	'''Returns branch of an app'''
	try:
		return subprocess.check_output('cd ../apps/{0} && git rev-parse --abbrev-ref HEAD'.format(app),
			shell=True).strip()
	except Exception:
		return ''

def get_app_last_commit_ref(app):
	try:
		return subprocess.check_output('cd ../apps/{0} && git rev-parse HEAD'.format(app),
			shell=True).strip()[:7]
	except Exception:
		return ''
