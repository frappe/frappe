// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.on("Website Theme", {
	onload_post_render(frm) {
		frm.events.make_app_theme_selector(frm);
	},

	refresh(frm) {
		frm.clear_custom_buttons();
		frm.toggle_display(["module", "custom"], !frappe.boot.developer_mode);

		frm.trigger("set_default_theme_button_and_indicator");
		frm.trigger("make_app_theme_selector");

		if (!frm.doc.custom && !frappe.boot.developer_mode) {
			frm.set_read_only();
			frm.disable_save();
		} else {
			frm.enable_save();
		}
	},

	set_default_theme_button_and_indicator(frm) {
		frappe.db.get_single_value("Website Settings", "website_theme").then((value) => {
			if (value === frm.doc.name) {
				frm.page.set_indicator(__("Default Theme"), "green");
			} else {
				frm.page.clear_indicator();
				// show set as default button
				if (!frm.is_new() && !frm.is_dirty()) {
					frm.add_custom_button(__("Set as Default Theme"), () => {
						frm.call("set_as_default").then(() => frm.trigger("refresh"));
					});
				}
			}
		});
	},

	make_app_theme_selector(frm) {
		if (frm.app_theme_selector) {
			frm.events.get_installed_apps(frm).then((apps) => {
				let ignored_apps = (frm.doc.ignored_apps || []).map((d) => d.app);
				frm.app_theme_selector
					.get_field("apps")
					.select_options(
						apps.map((d) => d.name).filter((app) => !ignored_apps.includes(app))
					);
			});
			return;
		}
		let $wrapper = frm.get_field("ignored_apps").$wrapper.hide();
		let $body = $("<div>").insertAfter($wrapper);
		let ignored_apps = (frm.doc.ignored_apps || []).map((d) => d.app);
		frm.events.get_installed_apps(frm).then((apps) => {
			if (frm.app_theme_selector) return;
			let form = new frappe.ui.FieldGroup({
				fields: [
					{
						label: __("Include Theme from Apps"),
						fieldname: "apps",
						fieldtype: "MultiCheck",
						columns: 4,
						on_change: () => {
							let value = form
								.get_field("apps")
								.get_unchecked_options()
								.map((app) => ({ app: app }));
							frm.set_value("ignored_apps", value.length ? value : null);
						},
						options: apps.map((app) => ({
							label: app.title,
							value: app.name,
							checked: !ignored_apps.includes(app.name),
						})),
					},
				],
				body: $body,
			});
			form.make();
			frm.app_theme_selector = form;
			$(form.wrapper).find(".form-section").css({
				padding: 0,
				marginLeft: "-15px",
				marginRight: "-15px",
			});
		});
	},

	get_installed_apps(frm) {
		return new Promise((resolve) => {
			if (frm.installed_apps) {
				resolve(frm.installed_apps);
				return;
			}
			return frm.call("get_apps").then((r) => {
				frm.installed_apps = r.message;
				resolve(r.message);
			});
		});
	},
});
