// Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.energy_points');

Object.assign(frappe.energy_points, {
	get_points(points) {
		return `<span class='bold' style="color: ${points >= 0 ? '#45A163': '#e42121'}">
			${points > 0 ? '+': ''}${points}
		</span>`;
	},
	log_message(log) {
		const doc_link = frappe.utils.get_form_link(log.reference_doctype, log.reference_name, true);
		const owner_name = frappe.user.full_name(log.owner).bold();
		if (log.type === 'Appreciation') {
			return __('{0} appreciated on {1}', [owner_name, doc_link]);
		}
		if (log.type === 'Criticism') {
			return __('{0} criticized on {1}', [owner_name, doc_link]);
		}
		return __('via automatic rule {0} for {1}', [log.rule.bold(), doc_link]);
	},
	format_log(log, with_timestamp=true) {
		let formatted_log = `<span>
			${this.get_points(log.points)}&nbsp;${this.log_message(log)}
			${ with_timestamp ? '<span>&nbsp;-&nbsp;</span>' + frappe.datetime.comment_when(log.creation):''}
		</span>`;
		return formatted_log;
	},
});