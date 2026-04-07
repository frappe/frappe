// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

/**
 * Document Template manager for form toolbar.
 *
 * For new (unsaved) documents — a "Templates ▾" dropdown is shown left of Save/Submit:
 *   • "Save as Template"  — captures only user-modified form fields
 *   • Inline list of templates  — click any to apply immediately
 *   • "Manage Templates"  — opens the full manage dialog (overwrite / delete)
 *
 * For saved documents — "Manage Templates" is added to the three-dot (⋮) menu.
 *
 * Templates are fetched via the standard frappe.client.get_list API and filtered
 * on the client side. Manageable templates (owner's own + System Manager) are derived
 * on the client side from the owner field.
 */
frappe.ui.form.DocumentTemplate = class DocumentTemplate {
	constructor({ frm, page }) {
		this.frm = frm;
		this.page = page;
		this.$group = null;
		this._templates_promise = null;
		this._template_data_cache = new Map();
		this._cache_invalidated = false;
	}

	_is_manageable(template) {
		if (frappe.session.user === "Administrator") return true;
		if (frappe.user_roles.includes("System Manager")) return true;
		return template.owner === frappe.session.user;
	}

	_invalidate_cache() {
		this._templates_promise = null;
		this._template_data_cache.clear();
		this._cache_invalidated = true;
	}

	_should_include_field(df) {
		if (cint(df.no_copy) || cint(df.read_only) || cint(df.hidden)) return false;
		return true;
	}

	_fetch_templates() {
		if (!this._templates_promise) {
			const meta = frappe.get_meta(this.frm.doctype);
			const preloaded = meta?.__document_templates;
			if (Array.isArray(preloaded) && !this._cache_invalidated) {
				this._templates_promise = Promise.resolve(preloaded);
			} else {
				this._templates_promise = frappe
					.call({
						method: "frappe.client.get_list",
						args: {
							doctype: "Document Template",
							fields: ["name", "template_name", "owner", "private", "disabled"],
							filters: { reference_doctype: this.frm.doctype },
							order_by: "private desc",
						},
					})
					.then((r) => r.message || []);
			}
		}
		return this._templates_promise;
	}

	setup_buttons() {
		if (!this.frm.doc.__islocal) {
			this.remove_buttons();
			return;
		}

		this._create_dropdown();
		this.$group.removeClass("hide");
	}

	remove_buttons() {
		this.$group?.addClass("hide");
	}

	_create_dropdown() {
		if (this.$group?.length) return;
		this.$group = this.page.get_or_add_inner_group_button(__("Templates"), true);
		this.page.btn_primary.before(this.$group);
		this._append_dt_item(__("Save as Template"), () => this.show_save_dialog());
		this._populate_dropdown();
	}
	_append_dt_item(label, action, cls, suffix_html = "") {
		const inner = suffix_html
			? `<span class="dt-item-text">${label}</span><span class="dt-item-icon text-extra-muted">${suffix_html}</span>`
			: label;
		return $(
			`<a class="dropdown-item${cls ? " " + cls : ""}${
				suffix_html ? " dt-item--with-suffix" : ""
			}" href="#"
				onclick="return false;"
				data-label="${label}">${inner}</a>`
		)
			.on("click", action)
			.appendTo(this.$group.find(".dropdown-menu"));
	}

	_append_dt_divider(cls) {
		$(`<li class="dropdown-divider${cls ? " " + cls : ""}"></li>`).appendTo(
			this.$group.find(".dropdown-menu")
		);
	}

	_populate_dropdown() {
		let $menu = this.$group.find(".dropdown-menu");

		this._fetch_templates().then((templates) => {
			$menu.find(".dt-dynamic").remove();

			let active = templates.filter((t) => !t.disabled);

			if (active.length) {
				this._append_dt_divider("dt-dynamic");
				for (let t of active) {
					const lock = t.private ? frappe.utils.icon("lock", "xs") : "";
					this._append_dt_item(
						t.template_name,
						() => this._apply_template(t.name, t.template_name),
						"dt-dynamic",
						lock
					);
				}
			}

			let manageable = templates.filter((t) => this._is_manageable(t));
			if (manageable.length) {
				this._append_dt_divider("dt-dynamic");
				this._append_dt_item(
					__("Manage Templates"),
					() => this.show_manage_dialog(),
					"dt-dynamic"
				);
			}
		});
	}

	add_template_menu_section() {
		if (this.frm.doc.__islocal) return;

		this.page.add_divider();

		this.page.add_menu_item(__("Save as Template"), () => this.show_save_dialog(), true);

		const $manage_item = this.page.add_menu_item(
			__("Manage Templates"),
			() => this.show_manage_dialog(),
			true
		);
		$manage_item.addClass("hide");

		this._fetch_templates()
			.then((templates) => {
				let manageable = templates.filter((t) => this._is_manageable(t));
				if (manageable.length) $manage_item.removeClass("hide");
			})
			.catch(() => {});
	}

	show_save_dialog() {
		let dialog = new frappe.ui.Dialog({
			title: __("Save as Template"),
			fields: [
				{
					fieldtype: "Data",
					fieldname: "template_name",
					label: __("Template Name"),
					reqd: 1,
					placeholder: __("e.g. Standard {0}", [__(this.frm.doctype)]),
					description: __(
						"Only fields you have modified from their defaults will be saved. Can be applied to any new {0}.",
						[__(this.frm.doctype)]
					),
				},
				{
					fieldtype: "Check",
					fieldname: "is_private",
					label: __("Private"),
					default: 0,
					description: __(
						"When enabled, only you can see and use this template. Uncheck to share it with everyone."
					),
				},
			],
			primary_action_label: __("Save"),
			primary_action: (values) => {
				const template_name = (values.template_name || "").trim();
				const captured = this._capture_template_data();
				if (!captured) {
					frappe.show_alert({
						message: __(
							"No data to save. Change at least one field before saving as a template."
						),
						indicator: "orange",
					});
					return;
				}

				dialog.disable_primary_action();

				frappe.db
					.insert({
						doctype: "Document Template",
						reference_doctype: this.frm.doctype,
						template_name,
						private: values.is_private ? 1 : 0,
						data: JSON.stringify(captured),
					})
					.then(() => {
						dialog.hide();
						frappe.show_alert({
							message: __("Template {0} saved.", [template_name]),
							indicator: "green",
						});

						if (this.$group) {
							this._invalidate_cache();
							this._populate_dropdown();
						}
					})
					.catch((e) => {
						console.error("Document Template: failed to save template", e);
						frappe.show_alert({
							message: __("Failed to save template {0}.", [template_name]),
							indicator: "red",
						});
					})
					.finally(() => {
						dialog.enable_primary_action();
					});
			},
		});

		dialog.show();
		dialog.fields_dict.template_name.$input.focus();
	}

	_capture_template_data() {
		let frm = this.frm;
		let doctype = frm.doctype;
		let doc = frm.doc;

		let result = {};

		for (let df of frappe.meta.get_docfields(doctype)) {
			if (!this._should_include_field(df)) continue;
			let current = doc[df.fieldname];

			if (frappe.model.table_fields.includes(df.fieldtype)) {
				let child_docfields = frappe.meta
					.get_docfields(df.options)
					.filter((cdf) => this._should_include_field(cdf));

				let rows = (current || [])
					.map((row) => {
						let clean = {};
						for (let cdf of child_docfields) {
							let child_val = row[cdf.fieldname];
							if (child_val !== cdf.__default_value) {
								clean[cdf.fieldname] = child_val;
							}
						}
						return clean;
					})
					.filter((r) => Object.keys(r).length);

				if (rows.length) {
					result[df.fieldname] = rows;
				}
				continue;
			}
			if (current !== df.__default_value) {
				result[df.fieldname] = current;
			}
		}

		return result;
	}

	show_manage_dialog() {
		this._fetch_templates().then((all_templates) => {
			let manageable = all_templates.filter((t) => this._is_manageable(t));

			let dialog = new frappe.ui.Dialog({
				title: __("Manage Templates"),
				fields: [{ fieldtype: "HTML", fieldname: "content_html" }],
				size: "small",
			});

			let $content = dialog.fields_dict.content_html.$wrapper;
			$content.html('<div class="dt-manage-list"></div>');
			let $wrap = $content.find(".dt-manage-list");

			let rerender = () => this._render_manage_list($wrap, manageable);
			let on_change = (deleted_name) => {
				if (deleted_name) {
					manageable = manageable.filter((t) => t.name !== deleted_name);
				}
				rerender();
				this._invalidate_cache();
				this._populate_dropdown();
			};

			$wrap.on("click.dtmanage", ".dt-template-update", (e) => {
				e.preventDefault();
				e.stopPropagation();
				const $btn = $(e.currentTarget);
				const name = $btn.attr("data-name");
				const label = $btn.attr("data-label") || "";

				frappe.confirm(
					__(
						"Replace template {0} with the current form values? This cannot be undone.",
						[label.bold()]
					),
					() => {
						frappe.db
							.set_value(
								"Document Template",
								name,
								"data",
								JSON.stringify(this._capture_template_data())
							)
							.then(() => {
								this._template_data_cache.delete(name);
								frappe.show_alert({
									message: __("Template {0} updated.", [label]),
									indicator: "green",
								});
								rerender();
							})
							.catch((err) => {
								console.error("Document Template: failed to update template", err);
								frappe.show_alert({
									message: __("Failed to update template {0}.", [label]),
									indicator: "red",
								});
							});
					}
				);
			});

			$wrap.on("click.dtmanage", ".dt-template-delete", (e) => {
				e.preventDefault();
				e.stopPropagation();

				const $btn = $(e.currentTarget);
				const name = $btn.attr("data-name");
				const label = $btn.attr("data-label") || "";

				if (!name) return;

				frappe.confirm(__("Delete template {0}?", [label.bold()]), () => {
					frappe.db
						.delete_doc("Document Template", name)
						.then(() => {
							frappe.show_alert({
								message: __("Template {0} deleted.", [label]),
								indicator: "green",
							});
							on_change(name);
						})
						.catch((err) => {
							console.error("Document Template: failed to delete template", err);
							frappe.show_alert({
								message: __("Failed to delete template {0}.", [label]),
								indicator: "red",
							});
						});
				});
			});

			dialog.show();
			rerender();
		});
	}

	_render_manage_list($wrap, templates) {
		$wrap.empty();

		if (!templates.length) {
			$wrap.html(
				'<div class="text-center text-muted py-4">' +
					'<p class="mb-0">' +
					__("No templates found.") +
					"</p>" +
					"</div>"
			);
			return;
		}

		templates.forEach((t, idx) => {
			let is_last = idx === templates.length - 1;
			let $row = $('<div class="dt-manage-row"></div>');
			if (is_last) $row.addClass("dt-manage-row--last");
			if (t.disabled) $row.addClass("dt-manage-row--disabled");

			let $label = $('<div class="dt-manage-row-label ellipsis"></div>')
				.attr("title", t.template_name)
				.text(t.template_name);

			if (t.disabled) {
				$label.append(
					$('<span class="text-muted ml-1"></span>').text("(" + __("Disabled") + ")")
				);
			}

			let $actions = $('<div class="dt-manage-row-actions"></div>');

			if (t.private) {
				$('<span class="text-extra-muted mr-1"></span>')
					.html(frappe.utils.icon("lock", "xs"))
					.attr("title", __("Private"))
					.appendTo($actions);
			}

			$('<button class="btn btn-xs btn-default"></button>')
				.attr("type", "button")
				.addClass("dt-template-update")
				.attr("data-name", t.name)
				.attr("data-label", t.template_name)
				.text(__("Update"))
				.attr("title", __("Replace with current form values"))
				.appendTo($actions);

			$('<a class="btn btn-xs btn-default"></a>')
				.attr("href", frappe.utils.get_form_link("Document Template", t.name))
				.attr("title", __("Open template"))
				.attr("aria-label", __("Edit {0}", [t.template_name]))
				.html(frappe.utils.icon("edit", "xs"))
				.appendTo($actions);

			$('<button class="btn btn-xs btn-default"></button>')
				.attr("type", "button")
				.addClass("dt-template-delete")
				.attr("data-name", t.name)
				.attr("data-label", t.template_name)
				.attr("title", __("Delete template"))
				.attr("aria-label", __("Delete {0}", [t.template_name]))
				.html(frappe.utils.icon("trash", "xs"))
				.appendTo($actions);

			$row.append($label, $actions);
			$wrap.append($row);
		});
	}

	_apply_template(name, label) {
		let fetch = this._template_data_cache.has(name)
			? Promise.resolve(this._template_data_cache.get(name))
			: frappe.db.get_value("Document Template", name, "data").then(({ message }) => {
					let raw = message?.data ?? null;
					if (raw) this._template_data_cache.set(name, raw);
					return raw;
			  });

		fetch.then((raw) => {
			if (!raw) {
				frappe.show_alert({
					message: __("Template data not found."),
					indicator: "orange",
				});
				return;
			}

			let doc = JSON.parse(raw);
			this._apply_to_form(doc, label);
		});
	}

	async _apply_to_form(doc, label) {
		let frm = this.frm;
		let field_updates = {};

		for (let df of frappe.meta.get_docfields(frm.doctype)) {
			if (!this._should_include_field(df)) continue;
			if (!(df.fieldname in doc)) continue;

			if (frappe.model.table_fields.includes(df.fieldtype)) {
				let child_rows = [];
				for (let src_row of doc[df.fieldname] || []) {
					let row_data = {};
					for (let cdf of frappe.meta.get_docfields(df.options)) {
						if (cint(df.no_copy)) continue;
						if (!(cdf.fieldname in src_row)) continue;
						row_data[cdf.fieldname] = src_row[cdf.fieldname];
					}
					if (Object.keys(row_data).length) {
						child_rows.push(row_data);
					}
				}
				if (child_rows.length) {
					field_updates[df.fieldname] = child_rows;
				}
			} else {
				field_updates[df.fieldname] = doc[df.fieldname];
			}
		}

		if (Object.keys(field_updates).length) {
			await frm.set_value(field_updates);
		}

		frm.dirty();

		frappe.show_alert({
			message: label ? __("Template {0} applied.", [label]) : __("Template applied."),
			indicator: "green",
		});
	}
};
