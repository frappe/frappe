frappe.provide('frappe.model.user_settings');

$.extend(frappe.model.user_settings, {
	save: function(doctype, key, value) {
		var user_settings = frappe.model.user_settings[doctype] || {};

		if ($.isPlainObject(value)) {
			$.extend(user_settings[key], value);
		} else {
			user_settings[key] = value;
		}

		return this.update(doctype, user_settings);
	},
	remove: function(doctype, key) {
		var user_settings = frappe.model.user_settings[doctype] || {};
		delete user_settings[key];

		return this.update(doctype, user_settings);
	},
	update: function(doctype, user_settings) {
		return frappe.call({
			method: 'frappe.model.utils.user_settings.save',
			args: {
				doctype: doctype,
				user_settings: user_settings
			},
			callback: function(r) {
				frappe.model.user_settings[doctype] = r.message;
			}
		})
	}
});

frappe.get_user_settings = function(doctype, key) {
	var settings = frappe.model.user_settings[doctype] || {};
	if(key) {
		settings = settings[key] || {};
	}
	return settings;
}