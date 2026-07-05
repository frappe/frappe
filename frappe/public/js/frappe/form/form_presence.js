frappe.ui.form.FormPresence = class FormPresence {
	constructor({ frm }) {
		this.frm = frm;
		this.parent = $('<div class="form-presence-viewers d-flex"></div>').prependTo(
			this.frm.page.page_actions
		);
		this.users_by_doc = {};
		this.last_published_target = {};
		this.publish_presence = frappe.utils.debounce((target) => this.publish(target), 150);
		this.setup_events();
	}

	get docname() {
		return this.frm?.doc?.name;
	}

	get active_users() {
		return this.users_by_doc[this.docname] || [];
	}

	set active_users(users) {
		if (!this.docname) return;
		this.users_by_doc[this.docname] = users;
	}

	get viewer_users() {
		return this.viewers_by_doc?.[this.docname] || [];
	}

	set viewer_users(users) {
		if (!this.docname) return;
		this.viewers_by_doc ??= {};
		this.viewers_by_doc[this.docname] = users;
	}

	setup_events() {
		this.frm.$wrapper
			.on("focusin.form-presence", ".frappe-control", (event) => {
				const field = event.currentTarget.fieldobj;
				const target = this.get_field_target(field);
				target && this.update_presence(target);
			})
			.on("focusout.form-presence", ".frappe-control", () => {
				setTimeout(() => {
					const is_in_control = this.frm.$wrapper
						.find(".frappe-control")
						.filter(function () {
							return (
								this === document.activeElement ||
								$.contains(this, document.activeElement)
							);
						}).length;
					if (!is_in_control) {
						this.update_tab_presence();
					}
				});
			});

		this.on_doc_presence = (data) => this.update_users(data);
		frappe.realtime.off("doc_presence", this.on_doc_presence);
		frappe.realtime.on("doc_presence", this.on_doc_presence);

		this.on_doc_viewers = (data) => this.update_viewers(data);
		frappe.realtime.off("doc_viewers", this.on_doc_viewers);
		frappe.realtime.on("doc_viewers", this.on_doc_viewers);
	}

	get_field_target(field) {
		if (!field?.df?.fieldname || this.frm.is_new()) return null;

		const target = {
			type: "field",
			fieldname: field.df.fieldname,
			tab_fieldname: this.get_tab_fieldname(field),
		};

		if (field.layout?.is_child_table && field.doc) {
			target.child_doctype = field.doctype;
			target.child_docname = field.doc.name;
			target.parentfield = field.doc.parentfield;
			target.tab_fieldname = this.get_tab_fieldname(
				this.frm.fields_dict[field.doc.parentfield]
			);
		}

		return target;
	}

	get_tab_fieldname(field) {
		return field?.tab?.df?.fieldname || this.frm.layout?.tabs?.[0]?.df?.fieldname || "";
	}

	set_current_tab(tab) {
		if (this.frm.is_new()) return;
		this.update_presence({ type: "tab", tab_fieldname: tab?.df?.fieldname || "" });
		this.refresh();
	}

	update_tab_presence() {
		const tab = this.frm.get_active_tab?.();
		if (tab) {
			this.set_current_tab(tab);
		} else {
			this.clear_presence();
		}
	}

	update_presence(target) {
		if (!this.frm.doc || this.frm.is_new()) return;

		const key = JSON.stringify(target || {});
		if (this.last_published_target[this.docname] === key) return;

		this.last_published_target[this.docname] = key;
		this.publish_presence(target);
	}

	publish(target) {
		if (!this.frm.doc || this.frm.is_new()) return;
		frappe.realtime.doc_presence_update(this.frm.doctype, this.frm.docname, target);
	}

	clear_presence() {
		if (!this.frm.doc || this.frm.is_new()) return;
		delete this.last_published_target[this.docname];
		frappe.realtime.doc_presence_clear(this.frm.doctype, this.frm.docname);
	}

	clear_indicators() {
		this.frm.$wrapper.find(".form-presence-users").remove();
		this.parent.empty();
	}

	async update_users({ doctype, docname, users = [] }) {
		if (this.frm?.doc?.doctype !== doctype || this.frm?.doc?.name !== docname) return;

		users = users.filter(({ sid, user }) => {
			if (sid && frappe.realtime.socket?.id) {
				return sid !== frappe.realtime.socket.id;
			}
			return user !== frappe.session.user;
		});
		await this.fetch_user_info(users.map(({ user }) => user));

		this.active_users = users;
		this.refresh();
	}

	async update_viewers({ doctype, docname, users = [] }) {
		if (this.frm?.doc?.doctype !== doctype || this.frm?.doc?.name !== docname) return;

		users = users.filter((user) => user !== frappe.session.user);
		await this.fetch_user_info(users);

		this.viewer_users = users;
		this.refresh();
	}

	async fetch_user_info(users) {
		const unknown_users = users.filter((user) => !frappe.boot.user_info[user]);
		if (!unknown_users.length) return;

		const data = await frappe.xcall("frappe.desk.form.load.get_user_info_for_viewers", {
			users: unknown_users,
		});
		Object.assign(frappe.boot.user_info, data);
	}

	refresh() {
		this.clear_indicators();

		const field_users = {};
		const tab_users = {};
		const document_users = this.viewer_users.filter(
			(user) => !this.active_users.some((active_user) => active_user.user === user)
		);
		for (const { user, target } of this.active_users) {
			if (target?.type === "field" && this.should_show_on_field(target)) {
				const key = this.get_field_key(target);
				field_users[key] ??= [];
				field_users[key].push(user);
			} else if (this.should_show_on_tab(target)) {
				const key =
					target?.tab_fieldname || this.frm.layout?.tabs?.[0]?.df?.fieldname || "";
				tab_users[key] ??= [];
				tab_users[key].push(user);
			} else {
				document_users.push(user);
			}
		}

		for (const [key, users] of Object.entries(field_users)) {
			this.render_field_users(key, users);
		}
		for (const [tab_fieldname, users] of Object.entries(tab_users)) {
			this.render_tab_users(tab_fieldname, users);
		}
		this.render_document_users(document_users);
	}

	should_show_on_field(target) {
		if (
			target.tab_fieldname &&
			this.frm.get_active_tab?.()?.df?.fieldname !== target.tab_fieldname
		) {
			return false;
		}
		return Boolean(this.get_field_wrapper(target)?.is(":visible"));
	}

	should_show_on_tab(target) {
		const tab_fieldname = target?.tab_fieldname || this.frm.layout?.tabs?.[0]?.df?.fieldname;
		const tab = this.get_tab(tab_fieldname);
		return Boolean(tab && !tab.is_hidden());
	}

	get_tab(tab_fieldname) {
		if (!tab_fieldname) return null;
		return this.frm.layout?.tabs?.find((tab) => tab.df.fieldname === tab_fieldname);
	}

	get_field_key(target) {
		return [target.child_doctype || "", target.child_docname || "", target.fieldname].join(
			":"
		);
	}

	get_field_wrapper(target) {
		if (target.child_docname) {
			return this.frm.$wrapper
				.find(`.frappe-control[data-fieldname="${target.fieldname}"]`)
				.filter(function () {
					return this.fieldobj?.doc?.name === target.child_docname;
				});
		}

		return this.frm.fields_dict[target.fieldname]?.$wrapper;
	}

	render_field_users(key, users) {
		const target = this.active_users.find(
			({ target }) => target?.type === "field" && this.get_field_key(target) === key
		)?.target;
		const $wrapper = this.get_field_wrapper(target);
		if (!$wrapper?.length) return;

		const $target = $wrapper.find(".clearfix").first();
		const $indicator = $('<span class="form-presence-users"></span>').appendTo($target);
		$indicator.append(this.make_avatar_group(users));
	}

	render_tab_users(tab_fieldname, users) {
		if (!tab_fieldname) return;

		const tab = this.get_tab(tab_fieldname);
		if (!tab) return;

		const $indicator = $('<span class="form-presence-users"></span>').appendTo(
			tab.tab_link.find(".nav-link")
		);
		$indicator.append(this.make_avatar_group(users));
	}

	render_document_users(users) {
		if (!users.length) return;
		this.parent.append(this.make_avatar_group(users));
	}

	make_avatar_group(users) {
		return frappe.avatar_group(users, 3, {
			css_class: "form-presence-avatar",
			overlap: true,
		});
	}
};
