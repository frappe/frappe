frappe.ui.form.on("System Settings", {
	refresh: function (frm) {
		frappe.call({
			method: "frappe.core.doctype.system_settings.system_settings.load",
			callback: function (data) {
				frappe.all_timezones = data.message.timezones;
				frm.set_df_property("time_zone", "options", frappe.all_timezones);

				$.each(data.message.defaults, function (key, val) {
					frm.set_value(key, val, null, true);
					frappe.sys_defaults[key] = val;
				});
				if (frm.re_setup_moment) {
					frappe.app.setup_moment();
					delete frm.re_setup_moment;
				}
			},
		});

		frappe.xcall("frappe.apps.get_apps").then((r) => {
			let apps = r?.map((r) => r.name) || [];
			frm.set_df_property("default_app", "options", [" ", ...apps]);
		});

		frm.trigger("set_rounding_method_options");
	},
	enable_password_policy: function (frm) {
		if (frm.doc.enable_password_policy == 0) {
			frm.set_value("minimum_password_score", "");
		} else {
			frm.set_value("minimum_password_score", "2");
		}
	},
	enable_two_factor_auth: function (frm) {
		if (frm.doc.enable_two_factor_auth == 0) {
			frm.set_value("bypass_2fa_for_retricted_ip_users", 0);
			frm.set_value("bypass_restrict_ip_check_if_2fa_enabled", 0);
		}
	},
	after_save: function (frm) {
		/**
		 * Checks whether the effective value has changed.
		 *
		 * @param {Array.<string>} - Tuple with new fallback, previous fallback and
		 *   optionally an override value.
		 * @returns {boolean} - Whether the resulting value has effectively changed
		 */
		const has_effectively_changed = ([new_fallback, prev_fallback, override = undefined]) =>
			!override && prev_fallback !== new_fallback;

		const attr_tuples = [
			[frm.doc.language, frappe.boot.sysdefaults.language, frappe.boot.user.language],
			[frm.doc.rounding_method, frappe.boot.sysdefaults.rounding_method], // no user override.
		];

		if (attr_tuples.some(has_effectively_changed)) {
			frappe.msgprint(__("Refreshing..."));
			window.location.reload();
		}
	},
	first_day_of_the_week(frm) {
		frm.re_setup_moment = true;
	},

	rounding_method: function (frm) {
		if (frm.doc.rounding_method == frappe.boot.sysdefaults.rounding_method) return;
		let msg = __(
			"Changing rounding method on site with data can result in unexpected behaviour."
		);
		msg += "<br>";
		msg += __("Do you still want to proceed?");

		frappe.confirm(
			msg,
			() => {},
			() => {
				frm.set_value("rounding_method", frappe.boot.sysdefaults.rounding_method);
			}
		);
	},

	set_rounding_method_options: function (frm) {
		if (frm.doc.rounding_method != "Banker's Rounding (legacy)") {
			let field = frm.fields_dict.rounding_method;

			field.df.options = field.df.options
				.split("\n")
				.filter((o) => o != "Banker's Rounding (legacy)")
				.join("\n");

			field.refresh();
		}
	},
});
