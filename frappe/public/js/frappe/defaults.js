// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.defaults = {
	get_user_default: function (key) {
		let defaults = frappe.boot.user.defaults;
		let d = defaults[key];
		if (!d && frappe.defaults.is_a_user_permission_key(key)) {
			d = defaults[frappe.model.scrub(key)];
			// Check for default user permission values
			let user_default = this.get_user_permission_default(key, defaults);
			if (user_default) d = user_default;
		}
		if ($.isArray(d)) d = d[0];

		if (!frappe.defaults.in_user_permission(key, d)) {
			return;
		}

		return d;
	},

	get_user_permission_default: function (key, defaults) {
		let permissions = this.get_user_permissions();
		let user_default = null;
		if (permissions[key]) {
			permissions[key].forEach((item) => {
				if (defaults[key] == item.doc) {
					user_default = item.doc;
				}
			});

			permissions[key].forEach((item) => {
				if (item.is_default) {
					user_default = item.doc;
				}
			});
		}

		return user_default;
	},

	get_user_defaults: function (key) {
		var defaults = frappe.boot.user.defaults;
		var d = defaults[key];

		if (frappe.defaults.is_a_user_permission_key(key)) {
			if (d && $.isArray(d) && d.length === 1) {
				// Use User Permission value when only when it has a single value
				d = d[0];
			} else {
				d = defaults[key] || defaults[frappe.model.scrub(key)];
			}
		}
		if (!$.isArray(d)) d = [d];

		// filter out values which are not permitted to the user
		d.filter((item) => {
			if (frappe.defaults.in_user_permission(key, item)) {
				return item;
			}
		});
		return d;
	},
	get_global_default: function (key) {
		var d = frappe.sys_defaults[key];
		if ($.isArray(d)) d = d[0];
		return d;
	},
	get_global_defaults: function (key) {
		var d = frappe.sys_defaults[key];
		if (!$.isArray(d)) d = [d];
		return d;
	},
	set_user_default_local: function (key, value) {
		frappe.boot.user.defaults[key] = value;
	},
	get_default: function (key) {
		var defaults = frappe.boot.user.defaults;
		var value = defaults[key];
		if (frappe.defaults.is_a_user_permission_key(key)) {
			if (value && $.isArray(value) && value.length === 1) {
				value = value[0];
			} else {
				value = defaults[frappe.model.scrub(key)];
			}
		}

		if (!frappe.defaults.in_user_permission(key, value)) {
			return;
		}

		if (value) {
			try {
				return JSON.parse(value);
			} catch (e) {
				return value;
			}
		}
	},

	is_a_user_permission_key: function (key) {
		return key.indexOf(":") === -1 && key !== frappe.model.scrub(key);
	},

	in_user_permission: function (key, value) {
		let user_permission = this.get_user_permissions()[frappe.model.unscrub(key)];

		if (user_permission && user_permission.length) {
			return user_permission.some((perm) => {
				return perm.doc === value;
			});
		} else {
			// there is no user permission for this doctype
			// so we can allow this doc i.e., value
			return true;
		}
	},

	get_user_permissions: function () {
		return this._user_permissions || {};
	},

	update_user_permissions: function () {
		const method = "frappe.core.doctype.user_permission.user_permission.get_user_permissions";
		frappe.call(method).then((r) => {
			if (r.message) {
				this._user_permissions = Object.assign({}, r.message);
			}
		});
	},

	load_user_permission_from_boot: function () {
		if (frappe.boot.user.user_permissions) {
			this._user_permissions = Object.assign({}, frappe.boot.user.user_permissions);
		} else {
			frappe.defaults.update_user_permissions();
		}
	},
};
