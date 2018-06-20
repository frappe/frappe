frappe.listview_settings['Chat Profile'] = 
{
	get_indicator: function (doc)
	{
		const status = frappe.utils.squash(frappe.chat.profile.STATUSES.filter(
			s => s.name === doc.status
		));

		return [__(status.name), status.color, `status,=,${status.name}`]
	}
};