frappe.ui.form.FormViewers = class FormViewers {
	constructor({ frm, parent }) {
		this.frm = frm;
		this.parent = parent;
		this.parent.tooltip({ title: __("Currently Viewing") });
		this.setup_events();
	}

	refresh() {
		let users = this.frm.get_docinfo()["viewers"];
		if (!users || !users.current || !users.current.length) {
			this.parent.empty();
			return;
		}

		let currently_viewing = users.current.filter((user) => user != frappe.session.user);
		let avatar_group = frappe.avatar_group(currently_viewing, 5, {
			align: "left",
			overlap: true,
		});
		this.parent.empty().append(avatar_group);
	}

	setup_events() {
		if (!this.initialized) {
			let me = this;
			frappe.realtime.on("doc_viewers", function (data) {
				me.update_users(data);
			});
		}
		this.initialized = true;
	}

	async update_users({ doctype, docname, users }) {
		const docinfo = frappe.model.get_docinfo(doctype, docname);
		const docinfo_key = "viewers";

		const past_users = ((docinfo && docinfo[docinfo_key]) || {}).past || [];
		users = users || [];
		const new_users = users.filter((user) => !past_users.includes(user));

		if (new_users.length === 0) return;

		await this.fetch_user_info(users);

		const info = {
			past: past_users.concat(new_users),
			new: new_users,
			current: users,
		};

		frappe.model.set_docinfo(doctype, docname, docinfo_key, info);

		if (
			cur_frm &&
			cur_frm.doc &&
			cur_frm.doc.doctype === doctype &&
			cur_frm.doc.name == docname &&
			cur_frm.viewers
		) {
			cur_frm.viewers.refresh(true);
		}
	}

	async fetch_user_info(users) {
		let unknown_users = [];
		for (let user of users) {
			if (!frappe.boot.user_info[user]) unknown_users.push(user);
		}
		if (!unknown_users) return;

		const data = await frappe.xcall("frappe.desk.form.load.get_user_info_for_viewers", {
			users: unknown_users,
		});
		Object.assign(frappe.boot.user_info, data);
	}
};
