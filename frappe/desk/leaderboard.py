
from __future__ import unicode_literals, print_function
import frappe

def get_leaderboards():
	leaderboards = {
		'Energy Point Log': {
			'fields': ['points'],
			'method': 'frappe.desk.leaderboard.get_energy_point_leaderboard',
		}
	}
	return leaderboards

def get_energy_point_leaderboard(from_date, company = None, field = None, limit = None):
	energy_point_users = frappe.db.get_all('Energy Point Log',
		fields = ['user as name', 'sum(points) as value'],
		filters = [
			['type', '!=', 'Review'],
			['creation', '>', from_date]
		],
		group_by = 'user',
		order_by = 'value desc'
	)
	all_users = frappe.db.get_all('User',
		filters = {'name': ['not in', ['Administrator', 'Guest']]},
		order_by = 'name ASC')

	all_users_list = list(map(lambda x: x['name'], all_users))
	energy_point_users_list = list(map(lambda x: x['name'], energy_point_users))
	for user in all_users_list:
		if user not in energy_point_users_list:
			energy_point_users.append({'name': user, 'value': 0})

	return energy_point_users