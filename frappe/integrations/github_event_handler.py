# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import json
import frappe
import frappe.utils
from frappe.social.doctype.energy_point_log.energy_point_log import ENERGY_POINT_VALUES, create_energy_point_log


@frappe.whitelist(allow_guest=True)
def handle_event(*args, **kwargs):
	r = frappe.request
	event_type = r.headers.get('X-Github-Event')
	payload = json.loads(r.get_data())
	if event_type == 'pull_request':
		process_pull_request(payload)
	if event_type == 'pull_request_review':
		process_pull_request(payload)
	elif event_type == 'issues':
		process_issues(payload)
	return True

def process_pull_request(payload):
	action = payload.get('action')
	data = payload.get('pull_request')
	user_github_id = data['user']['login']
	if not is_local_user(user_github_id): return
	if action == 'closed' and data['merged']:
		process_merged_pull_request(data)
	if action == 'submitted':
		process_pull_request_review(data)

def process_issues(payload):
	action = payload.get('action')
	data = payload.get('issue')
	user_github_id = data['user']['login']
	if not is_local_user(user_github_id): return
	if action == 'opened':
		create_energy_point_log(
			ENERGY_POINT_VALUES['github_issue_open'],
			'Opened Issue: {}'.format(data['title']),
			None,
			None,
			get_user_name(data['user']['login'])
		)
	if action == 'closed':
		create_energy_point_log(
			ENERGY_POINT_VALUES['github_issue_close'],
			'Closed Issue: {}'.format(data['title']),
			None,
			None,
			get_user_name(data['user']['login'])
		)

def process_merged_pull_request(data):
	create_energy_point_log(
		ENERGY_POINT_VALUES['github_pull_request_merge'],
		'Pull Request Merged: {}'.format(data['title']),
		None,
		None,
		get_user_name(data['user']['login'])
	)

def process_pull_request_review(data):
	create_energy_point_log(
		ENERGY_POINT_VALUES['github_pull_request_review_submit'],
		'Reviewed Pull Request: {}'.format(data['title']),
		None,
		None,
		get_user_name(data['user']['login'])
	)


def is_local_user(github_id):
	return frappe.db.count('Social Profile', {'github_id': github_id})

def get_user_name(github_id):
	return frappe.get_value('Social Profile', filters={
		'github_id': github_id
	}, fieldname='name')
