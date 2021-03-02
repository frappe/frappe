
from __future__ import unicode_literals, print_function
import frappe
from frappe.utils import get_fullname

def get_leaderboards():
	leaderboards = {
		'User': {
			'fields': ['points'],
			'method': 'frappe.desk.leaderboard.get_energy_point_leaderboard',
			'company_disabled': 1
		}
	}
	return leaderboards

@frappe.whitelist()
<<<<<<< HEAD
def get_energy_point_leaderboard(from_date, company = None, field = None, limit = None):
=======
def get_energy_point_leaderboard(date_range, company = None, field = None, limit = None):
	all_users = frappe.db.get_all('User',
		filters = {
			'name': ['not in', ['Administrator', 'Guest']],
			'enabled': 1,
			'user_type': ['!=', 'Website User']
		},
		order_by = 'name ASC')
	all_users_list = list(map(lambda x: x['name'], all_users))

	filters = [
		['type', '!=', 'Review'],
		['user', 'in', all_users_list]
	]
	if date_range:
		date_range = frappe.parse_json(date_range)
		filters.append(['creation', 'between', [date_range[0], date_range[1]]])
>>>>>>> 3cfb57cec1 (fix: don't show disabled users in leaderboard)
	energy_point_users = frappe.db.get_all('Energy Point Log',
		fields = ['user as name', 'sum(points) as value'],
		filters = [
			['type', '!=', 'Review'],
			['creation', '>', from_date]
		],
		group_by = 'user',
		order_by = 'value desc'
	)

	energy_point_users_list = list(map(lambda x: x['name'], energy_point_users))
	for user in all_users_list:
		if user not in energy_point_users_list:
			energy_point_users.append({'name': user, 'value': 0})

	for user in energy_point_users:
		user_id = user['name']
		user['name'] = get_fullname(user['name'])
		user['formatted_name'] = '<a href="#user-profile/{}">{}</a>'.format(user_id, get_fullname(user_id))

	return energy_point_users