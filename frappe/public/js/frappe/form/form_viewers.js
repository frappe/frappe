frappe.ui.form.FormViewers = class FormViewers {
	constructor({ frm, parent }) {
		this.frm = frm;
		this.parent = parent;
		this.parent.tooltip({ title: __('Currently Viewing') });
	}

	refresh() {
		let users = this.frm.get_docinfo()['viewers'];
		if (!users || !users.current || !users.current.length) {
			this.parent.empty();
			return;
		}

		let currently_viewing = users.current.filter(user => user != frappe.session.user);
		let avatar_group = frappe.avatar_group(currently_viewing, 5, {'align': 'left', 'overlap': true});
		this.parent.empty().append(avatar_group);
	}
};

frappe.ui.form.FormViewers.set_users = function(data, type) {
	const doctype = data.doctype;
	const docname = data.docname;
	const docinfo = frappe.model.get_docinfo(doctype, docname);

	const past_users = ((docinfo && docinfo[type]) || {}).past || [];
	const users = data.users || [];
	const new_users = users.filter(user => !past_users.includes(user));

	frappe.model.set_docinfo(doctype, docname, type, {
		past: past_users.concat(new_users),
		new: new_users,
		current: users
	});

	if (
		cur_frm &&
		cur_frm.doc &&
		cur_frm.doc.doctype === doctype &&
		cur_frm.doc.name == docname &&
		cur_frm.viewers
	) {
		cur_frm.viewers.refresh(true, type);
	}
};
