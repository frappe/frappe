import DeskSection from "./desk_section";

export default class Desk {
	constructor({ container }) {
		this.container = $(container);
		this.module_categories = [
			"Modules",
			"Domains",
			"Places",
			"Administration"
		];
		this.sections = {};
		this.make();
	}

	refresh() {
		this.modules_section_container &&
			this.modules_section_container.remove();
		this.make();
	}

	make() {
		this.fetch_desktop_settings().then(() => {
			this.make_container();
			this.make_sections();
			this.setup_events();
		});
	}

	fetch_desktop_settings() {
		return frappe
			.call("frappe.desk.moduleview.get_desktop_settings")
			.then(response => {
				if (response.message) {
					this.categories = response.message;
				}
			});
	}

	make_container() {
		this.modules_section_container = $(`<div class="desk-modules-page-container">
			<a class="btn-show-hide text-muted text-medium show-or-hide-cards">
				${__("Show / Hide Cards")}
			</a></div>`);

		this.modules_section_container.appendTo(this.container);
	}

	make_sections() {
		this.module_categories.forEach(category => {
			if (
				this.categories.hasOwnProperty(category) &&
				this.categories[category].length
			) {
				this.sections[category] = new DeskSection({
					title: category,
					options: { category: category },
					widget_config: this.categories[category],
					container: this.modules_section_container,
					sortable_config: {
						enable: true,
						after_sort: (container, options) => {
							let modules = Array.from(
								container.querySelectorAll(".module-box")
							).map(node => node.dataset.moduleName);

							frappe.call(
								"frappe.desk.moduleview.update_modules_order",
								{
									module_category: options.category,
									modules: modules
								}
							);
						}
					}
				});
			}
		});
	}

	setup_events() {
		const show_or_hide = this.modules_section_container.find(
			".show-or-hide-cards"
		);
		show_or_hide.on("click", () => this.setup_show_hide_cards());
	}

	setup_show_hide_cards() {
		const get_visible_cards_fields = (field_options, is_global = false) => {
			const fieldtype = is_global ? "global" : "user";

			return this.module_categories
				.map(category => {
					let options = field_options.filter(
						m => m.category === category
					);
					return {
						label: category,
						fieldname: `${fieldtype}:${category}`,
						fieldtype: "MultiCheck",
						options,
						columns: 2
					};
				})
				.filter(f => f.options.length > 0);
		};

		frappe
			.call("frappe.desk.moduleview.get_options_for_show_hide_cards")
			.then(r => {
				let { user_options, global_options } = r.message;

				let user_value = `User (${frappe.session.user})`;

				let user_section = get_visible_cards_fields(user_options);
				let global_section = get_visible_cards_fields(
					global_options,
					true
				);

				let fields = [
					{
						label: __("Setup For"),
						fieldname: "setup_for",
						fieldtype: "Select",
						options: [
							{
								label: __("My Account (User {0})", [
									frappe.session.user
								]),
								value: user_value
							},
							{
								label: __("Everyone"),
								value: "Everyone"
							}
						],
						default: user_value,
						depends_on: () =>
							frappe.user_roles.includes("System Manager"),
						onchange() {
							let value = dialog.get_value("setup_for");
							let field = dialog.get_field("setup_for");
							let description =
								value === "Everyone"
									? __("Hide cards for all users")
									: "";
							field.set_description(description);
						}
					},
					{
						fieldtype: "Section Break",
						depends_on: doc => doc.setup_for === user_value
					},
					...user_section,
					{
						fieldtype: "Section Break",
						depends_on: doc =>
							doc.setup_for === "Everyone" &&
							frappe.user_roles.includes("System Manager")
					},
					...global_section
				];

				let old_values = null;

				const dialog = new frappe.ui.Dialog({
					title: __("Show / Hide Cards"),
					fields: fields,
					primary_action_label: __("Save"),
					primary_action: values => {
						if (values.setup_for === "Everyone") {
							this.update_global_modules(dialog);
						} else {
							this.update_user_modules(dialog, old_values);
						}
					}
				});

				dialog.show();

				// deepcopy
				old_values = JSON.parse(JSON.stringify(dialog.get_values()));
			});
	}

	update_user_modules(d, old_values) {
		let new_values = d.get_values();
		let category_map = {};
		for (let category of this.module_categories) {
			let old_modules = old_values[`user:${category}`] || [];
			let new_modules = new_values[`user:${category}`] || [];

			let removed = old_modules.filter(
				module => !new_modules.includes(module)
			);
			let added = new_modules.filter(
				module => !old_modules.includes(module)
			);

			category_map[category] = { added, removed };
		}

		frappe
			.call({
				method: "frappe.desk.moduleview.update_hidden_modules",
				args: { category_map },
				btn: d.get_primary_btn()
			})
			.then(r => {
				this.refresh();
				d.hide();
			});
	}

	update_global_modules(d) {
		let blocked_modules = [];
		this.module_categories.forEach(category => {
			if (d.fields_dict[`global:${category}`]) {
				let unchecked_options = d.fields_dict[
					`global:${category}`
				].get_unchecked_options();
				blocked_modules = blocked_modules.concat(unchecked_options);
			}
		});

		frappe
			.call({
				method: "frappe.desk.moduleview.update_global_hidden_modules",
				args: {
					modules: blocked_modules
				},
				btn: d.get_primary_btn()
			})
			.then(() => {
				this.refresh();
				d.hide();
			});
	}
}
