import frappe

@frappe.whitelist()
def get_energy_points_heatmap_data(user, date):
	return dict(frappe.db.sql("""select unix_timestamp(date(creation)), sum(points)
		from `tabEnergy Point Log`
		where
			date(creation) > subdate('{date}', interval 1 year) and
			date(creation) < subdate('{date}', interval -1 year) and
			user = '{user}' and
			type != 'Review'
		group by date(creation)
		order by creation asc""".format(user=user, date = date)))


@frappe.whitelist()
def get_energy_points_pie_chart_data(user, field):
    result = frappe.db.get_all('Energy Point Log',
        filters={'user': user, 'type': ['!=', 'Review']},
        group_by=field, order_by = field,
        fields=[field, 'ABS(sum(points)) as points'],
        as_list = True)

    return {
        "labels": [r[0] for r in result if r[0]!=None],
        "datasets": [{
            "values": [r[1] for r in result]
        }]
    }

@frappe.whitelist()
def get_user_points_and_rank(user, date=None):
    result = frappe.db.get_all('Energy Point Log',
        group_by='user',
        filters={'creation': ['>', date], 'type' : ['!=', 'Review']},
        fields=['user', '(sum(points)) as points', 'rank() over (order by points desc) as rank'],
        as_list = True)

    return [r for r in result if r[0]==user]


@frappe.whitelist()
def update_profile_info(profile_info):
    profile_info = frappe.parse_json(profile_info)
    keys = ['location', 'interest', 'user_image', 'bio']

    for key in keys:
        if key not in profile_info:
            profile_info[key] = None

    user = frappe.get_doc('User', frappe.session.user)
    user.update(profile_info)
    user.save()
    return user

@frappe.whitelist()
def get_energy_points_list(start, limit, user):
    return frappe.db.get_list('Energy Point Log',filters = {'user': user, 'type': ['!=', 'Review']},
        fields=['name','user', 'points', 'reference_doctype', 'reference_name', 'reason',
            'type', 'seen', 'rule', 'owner', 'creation', 'revert_of'],
        start=start, limit=limit, order_by='creation desc')
