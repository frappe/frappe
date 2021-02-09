frappe.ui.form.SidebarUsers = class {
	constructor(opts) {
		$.extend(this, opts);
	}

	get_users(type) {
		let docinfo = this.frm.get_docinfo();
		return docinfo ? docinfo[type] || null: null;
	}

	refresh(data_updated, type) {
		this.parent = type == 'viewers'? this.$wrapper.find('.form-viewers'): this.$wrapper.find('.form-typers');
		this.parent.empty();

		const users = this.get_users(type);
		users && this.show_in_sidebar(users, type, data_updated);
	}

	show_in_sidebar(users, type, show_alert) {
		let sidebar_users = [];
		let new_users = [];
		let current_users = [];

		const message = type == 'viewers' ? 'viewing this document': 'composing an email';

		users.current.forEach(username => {
			if (username === frappe.session.user) {
				// current user
				return;
			}

			var user_info = frappe.user_info(username);
			sidebar_users.push({
				image: user_info.image,
				fullname: user_info.fullname,
				abbr: user_info.abbr,
				color: user_info.color,
				title: __("{0} is currently {1}", [user_info.fullname, message])
			});

			if (users.new.indexOf(username) !== -1) {
				new_users.push(user_info.fullname);
			}

			current_users.push(user_info.fullname);
		});

		if (sidebar_users.length) {
			this.parent.parent().removeClass('hidden');
			this.parent.append(frappe.render_template('users_in_sidebar', {'users': sidebar_users}));
		} else {
			this.parent.parent().addClass('hidden');
		}

		// For typers always show the alert
		// For viewers show the alert to new user viewing this document
		const alert_users = type == 'viewers' ? new_users : current_users;
		show_alert && this.show_alert(alert_users, message);
	}

	show_alert(users, message) {
		if (users.length) {
			if (users.length===1) {
				frappe.show_alert(__('{0} is currently {1}', [users[0], message]));
			} else {
				frappe.show_alert(__('{0} are currently {1}', [frappe.utils.comma_and(users), message]));
			}
		}
	}
};
