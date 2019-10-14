# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import frappe
import jwt
import time


@frappe.whitelist()
def get_url(dashboard):
	# get metabase info
	metabase_config = frappe.get_single('Metabase Settings')
	# get dashboard info
	dashboard = frappe.get_doc('Metabase Dashboard', dashboard)

	# config token
	payload = {
		'resource': {'dashboard': int(dashboard.dashboard_id)},
		'params': {},
	}
	# set expiration time
	exp_time = metabase_config.metabase_exp_time
	if exp_time:
		payload['exp'] = round(time.time()) + (60 * exp_time)  # 60 second * minute

	# gen token
	token = jwt.encode(
		payload,
		metabase_config.metabase_secret,
		algorithm='HS256'
	)

	# prepare config
	config = []
	if dashboard.show_border:
		config.append('bordered=true')
	else:
		config.append('bordered=false')
	if dashboard.show_title:
		config.append('titled=true')
	else:
		config.append('titled=false')
	if dashboard.theme == 'Dark':
		config.append('theme=night')
	config_param = '&'.join(config)

	# prepare url
	resizer = ''.join([
		metabase_config.metabase_url,
		'/app/iframeResizer.js',
	])
	iframeUrl = ''.join([
		metabase_config.metabase_url,
		'/embed/dashboard/',
		token.decode('utf8'),
		'#',
		config_param,
	])

	return {
		'name': dashboard.dashboard_name,
		'resizer': resizer,
		'iframeUrl': iframeUrl
	}