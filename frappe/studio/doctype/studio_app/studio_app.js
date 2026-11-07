// Copyright (c) 2024, Frappe Technologies Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Studio App", {
	refresh(frm) {
		frappe.xcall("frappe.core.doctype.module_def.module_def.get_installed_apps").then((r) => {
			const options = JSON.parse(r);
			options.unshift("");
			frm.set_df_property("frappe_app", "options", options);
		});

		if (!frappe.boot.developer_mode) {
			frm.set_df_property("is_standard", "read_only", 1);
			frm.set_df_property("frappe_app", "read_only", 1);
			if (frm.doc.is_standard) frm.disable_form();
		}
		setup_router_script_help(frm);
	},
	is_standard: setup_router_script_help,
});

function setup_router_script_help(frm) {
	const help_box = frm.fields_dict.router_script.$wrapper.find(".help-box");
	const existing = help_box.find(".router-script-help");
	if (existing.length) {
		existing.data("es-popover")?.close();
		return;
	}
	if (frm.doc.is_standard) return;

	const button = $('<button type="button" class="btn btn-link btn-xs router-script-help">')
		.text(__("View example"))
		.appendTo(help_box);
	const popover = new frappe.ui.Popover({
		trigger: button,
		css_class: "router-script-help-popover",
		content: () =>
			$("<div>")
				.append(
					$('<div class="es-popover__header">').append(
						$('<div class="es-popover__title">').text(__("Router script example"))
					),
					get_router_script_help()
				)
				.get(0),
	});
	button.data("es-popover", popover);
	$(frm.page.wrapper)
		.off("hide.router-script-help")
		.on("hide.router-script-help", () => popover.close());
}

function get_router_script_help() {
	const script = `{
  routerOptions: {
    scrollBehavior: () => ({ top: 0 }),
  },
  extendRoute(route) {
    if (route.name === 'Tasks') route.alias = '/todo'
  },
  setup(router) {
    router.beforeEach((to) => {
      if (window.boot.onboarding_complete === false && to.name !== 'Onboarding') {
        return { name: 'Onboarding' }
      }
    })
  },
}`;
	return $("<div>")
		.css("width", "min(560px, calc(100vw - 64px))")
		.append(
			$("<p>").text(
				__(
					"Write a JavaScript object without import or export statements. All fields are optional."
				)
			),
			$('<pre class="mb-2">').append($("<code>").text(script)),
			$('<p class="mb-0">').text(
				__(
					"Replace Tasks and Onboarding with your page titles. Provide boot.onboarding_complete through the studio_app_boot hook."
				)
			)
		);
}
