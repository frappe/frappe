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
    result = (frappe.db.sql("""select {field}, ABS(sum(points))
        from `tabEnergy Point Log`
        where
        user = '{user}' and
        type != 'Review'
        group by {field}
        order by {field}""".format(user=user, field=field)))
    # result = frappe.db.get_all('Energy Point Log', filters={'user': user, 'type': ['!=', 'Review']}, group_by='type', order_by = 'type', fields=['type', 'sum(points) as points'], as_list = True)
    print(result)
    return {
        "labels": [r[0] for r in result if r[0]!=None],
        "datasets": [{
            "values": [r[1] for r in result]
        }]
    }

@frappe.whitelist()
def get_user_points_and_rank(user, date=None):
    result = frappe.db.sql("""select user, sum(points) as points, rank() over (order by points desc) as rank
        from `tabEnergy Point Log`
        where creation > '{date}'
        group by user""".format(date=date))
    return [r for r in result if r[0]==user]


@frappe.whitelist()
def update_profile_info(profile_info):
	profile_info = frappe.parse_json(profile_info)
    #for loop
	if 'location' not in profile_info:
		profile_info['location'] = None
	if 'interest' not in profile_info:
		profile_info['interest'] = None
	if 'user_image' not in profile_info:
		profile_info['user_image'] = None
	if 'bio' not in profile_info:
		profile_info['bio'] = None
	user = frappe.get_doc('User', frappe.session.user)
	user.update(profile_info)
	user.save()
	return user

@frappe.whitelist()
def get_energy_points_list(start, limit, user):
    return frappe.db.get_list('Energy Point Log',filters = {'user': user, 'type': ['!=', 'Review']},
        fields=['name','user', 'points', 'reference_doctype', 'reference_name', 'reason', 'type', 'seen', 'rule', 'owner', 'creation'],
        start=start, limit=limit, order_by='creation desc')
