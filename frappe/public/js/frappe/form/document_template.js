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
 * All permission logic (visibility, edit, delete) is enforced server-side.
 */
frappe.ui.form.DocumentTemplate = class DocumentTemplate {
	static DOCTYPE = "Document Template";

	constructor({ frm, page }) {
		this.frm = frm;
		this.page = page;
		this.$group = null;
		this._loading_templates = false;
		this._loading_manage = false;
	}

	_can_use_templates() {
		if (this.frm.meta.issingle || this.frm.meta.hide_toolbar) return false;
		if (frappe.session.user === "Guest") return false;
		if (!frappe.model.can_create(this.frm.doctype)) return false;
		return true;
	}

	_get_templates() {
		return frappe.db.get_list(this.constructor.DOCTYPE, {
			fields: ["name", "template_name", "owner", "private"],
			filters: { reference_doctype: this.frm.doctype },
			order_by: "template_name asc",
		});
	}

	_get_manageable_templates() {
		return frappe
			.call({
				method: "frappe.desk.doctype.document_template.document_template.get_manageable_templates",
				args: { reference_doctype: this.frm.doctype },
			})
			.then((r) => r.message || []);
	}

	setup_buttons() {
		if (!this._can_use_templates()) return;
		if (!this.frm.doc.__islocal) {
			this.remove_buttons();
			return;
		}

		if (!this.$group) this._create_buttons();
		this.$group.removeClass("hide");
	}

	remove_buttons() {
		this.$group?.addClass("hide");
	}

	/**
	 * Called from toolbar.make_menu_items() to add "Manage Templates"
	 * to the three-dot (⋮) menu for already-saved documents.
	 */
	add_manage_menu_item() {
		if (!this._can_use_templates()) return;
		if (this.frm.doc.__islocal) return;

		const $item = this.page.add_menu_item(
			__("Manage Templates"),
			() => this.show_manage_dialog(),
			true
		);
		$item.addClass("hide");

		this._get_manageable_templates()
			.then((templates) => {
				if ((templates || []).length) $item.removeClass("hide");
			})
			.catch(() => {});
	}

	_create_buttons() {
		// Use Frappe's page component for the button group structure
		this.$group = this.page.get_or_add_inner_group_button(__("Templates"), true);
		const $menu = this.$group.find(".dropdown-menu");

		// Static: "Save as Template"
		$('<a class="dropdown-item dt-save-template" href="#">')
			.text(__("Save as Template"))
			.appendTo($menu);

		// Dynamic: divider + list of saved templates + divider + manage link
		$('<div class="dropdown-divider dt-list-divider hide">').appendTo($menu);
		$('<div class="dt-template-list">').appendTo($menu);
		$('<div class="dropdown-divider dt-manage-divider hide">').appendTo($menu);
		$('<a class="dropdown-item dt-manage-templates hide" href="#">')
			.text(__("Manage Templates"))
			.appendTo($menu);

		this.$group
			.on("click", ".dt-save-template", (e) => {
				e.preventDefault();
				this.show_save_dialog();
			})
			.on("click", ".dt-manage-templates", (e) => {
				e.preventDefault();
				this.show_manage_dialog();
			})
			.on("click", ".dt-template-apply", (e) => {
				e.preventDefault();
				const $link = $(e.currentTarget);
				this._apply_template($link.data("name"), $link.data("label"));
			})
			.on("show.bs.dropdown", () => {
				this._load_templates_into_dropdown();
			});

		this.page.btn_primary.before(this.$group);
	}

	_load_templates_into_dropdown() {
		if (this._loading_templates) return;
		this._loading_templates = true;
		const $list = this.$group.find(".dt-template-list");
		$list.html(`<span class="dropdown-item disabled text-muted">${__("Loading…")}</span>`);

		Promise.all([this._get_templates(), this._get_manageable_templates()])
			.then(([templates, manageable]) => {
				this._loading_templates = false;
				this._render_dropdown_templates(templates || [], (manageable || []).length);
			})
			.catch((e) => {
				console.error("Document Template: failed to load templates", e);
				this._loading_templates = false;
				$list.html(
					`<span class="dropdown-item disabled text-muted">${__(
						"Failed to load"
					)}</span>`
				);
			});
	}

	_render_dropdown_templates(templates, manageableCount = 0) {
		const $list = this.$group.find(".dt-template-list");
		const $list_divider = this.$group.find(".dt-list-divider");
		const $manage_divider = this.$group.find(".dt-manage-divider");
		const $manage_btn = this.$group.find(".dt-manage-templates");

		$list.empty();

		if (!templates.length) {
			$list_divider.removeClass("hide");
			$manage_divider.addClass("hide");
			$manage_btn.addClass("hide");
			$list.html(
				`<span class="dropdown-item disabled text-muted">${__(
					"No templates yet — save one above."
				)}</span>`
			);
			return;
		}

		$list_divider.removeClass("hide");
		$manage_divider.toggleClass("hide", !manageableCount);
		$manage_btn.toggleClass("hide", !manageableCount);

		const rows_html = templates
			.map((t) => {
				return `<a class="dropdown-item dt-template-apply ellipsis"
				   href="#"
				   data-name="${frappe.utils.escape_html(t.name)}"
				   data-label="${frappe.utils.escape_html(t.template_name)}"
				   title="${frappe.utils.escape_html(t.template_name)}">
					${frappe.utils.escape_html(t.template_name)}
				</a>`;
			})
			.join("");
		$list.html(rows_html);
	}

	show_save_dialog() {
		const dialog = new frappe.ui.Dialog({
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
				if (!values.template_name) return;
				dialog.disable_primary_action();

				frappe
					.call({
						method: "frappe.desk.doctype.document_template.document_template.create_template",
						args: {
							reference_doctype: this.frm.doctype,
							template_name: values.template_name,
							private: values.is_private ? 1 : 0,
							data: JSON.stringify(this._capture_template_data()),
						},
					})
					.then((r) => {
						if (!r?.message) {
							console.error("Document Template: create_template returned no name");
							frappe.show_alert({
								message: __("Failed to save template."),
								indicator: "red",
							});
							dialog.enable_primary_action();
							return;
						}

						dialog.hide();
						frappe.show_alert({
							message: __("Template {0} saved.", [
								frappe.utils.escape_html(values.template_name),
							]),
							indicator: "green",
						});
					})
					.catch((e) => {
						console.error("Document Template: failed to save template", e);
						dialog.enable_primary_action();
					});
			},
		});

		dialog.show();
		dialog.fields_dict.template_name.$input.focus();
	}

	_capture_template_data() {
		const frm = this.frm;
		const doctype = frm.doctype;
		const doc = frm.doc;

		const same_value = (fieldtype, a, b) => {
			if (["Int", "Long Int", "Check"].includes(fieldtype)) return cint(a) === cint(b);
			if (["Currency", "Float", "Percent"].includes(fieldtype)) return flt(a) === flt(b);
			const is_empty = (v) => v === null || v === undefined || v === "";
			if (is_empty(a) && is_empty(b)) return true;
			if (is_empty(a) || is_empty(b)) return false;
			return String(a) === String(b);
		};

		const result = { doctype };

		for (const df of frappe.meta.get_docfields(doctype)) {
			if (cint(df.no_copy)) continue;
			if (frappe.model.no_value_type.includes(df.fieldtype)) continue;

			const current = doc[df.fieldname];

			if (frappe.model.table_fields.includes(df.fieldtype)) {
				const rows = (current || []).map((row) => {
					const clean = {};
					for (const cdf of frappe.meta.get_docfields(df.options)) {
						if (!cint(cdf.no_copy)) {
							clean[cdf.fieldname] = row[cdf.fieldname];
						}
					}
					return clean;
				});
				if (rows.length) {
					result[df.fieldname] = rows;
				}
				continue;
			}
			const default_val =
				df.__default_value !== undefined ? df.__default_value : df.default ?? null;
			if (!same_value(df.fieldtype, current, default_val)) {
				result[df.fieldname] = current;
			}
		}

		return result;
	}

	show_manage_dialog() {
		if (this._loading_manage) return;
		this._loading_manage = true;
		this._get_manageable_templates()
			.then((templates) => {
				let all_templates = templates || [];

				const dialog = new frappe.ui.Dialog({
					title: __("Manage Templates"),
					fields: [{ fieldtype: "HTML", fieldname: "content_html" }],
					size: "small",
				});

				dialog.modal_body.css("padding-top", "var(--padding-sm)");

				const $content = dialog.fields_dict.content_html.$wrapper;

				$content.html(`<div class="dt-list-wrap"></div>`);

				const $wrap = $content.find(".dt-list-wrap");

				const render_list = () => this._render_manage_list($wrap, all_templates);

				dialog.show();
				render_list();
				dialog.$wrapper.one("hidden.bs.modal", () => {
					this._loading_manage = false;
				});

				$wrap.on("click", ".dt-overwrite", (e) => {
					e.stopPropagation();
					const $btn = $(e.currentTarget);
					const name = $btn.data("name");
					const label = frappe.utils.escape_html($btn.data("label"));

					frappe.confirm(
						__(
							"Replace template {0} with the current form values? This cannot be undone.",
							[label.bold()]
						),
						() => {
							frappe
								.call({
									method: "frappe.desk.doctype.document_template.document_template.update_template",
									args: {
										name,
										data: JSON.stringify(this._capture_template_data()),
									},
								})
								.then(() => {
									frappe.show_alert({
										message: __("Template {0} updated.", [label]),
										indicator: "green",
									});
								})
								.catch((e) => {
									console.error(
										"Document Template: failed to update template",
										e
									);
									frappe.show_alert({
										message: __("Failed to update template {0}.", [label]),
										indicator: "red",
									});
								});
						}
					);
				});

				$wrap.on("click", ".dt-template-delete", (e) => {
					e.stopPropagation();
					const $btn = $(e.currentTarget);
					const name = $btn.data("name");
					const label = frappe.utils.escape_html($btn.data("label"));

					frappe.confirm(__("Delete template {0}?", [label.bold()]), () => {
						frappe
							.call({
								method: "frappe.desk.doctype.document_template.document_template.delete_template",
								args: { name },
							})
							.then(() => {
								all_templates = all_templates.filter((t) => t.name !== name);
								render_list();
								frappe.show_alert({
									message: __("Template {0} deleted.", [label]),
									indicator: "green",
								});
							})
							.catch((e) => {
								console.error("Document Template: failed to delete template", e);
								frappe.show_alert({
									message: __("Failed to delete template {0}.", [label]),
									indicator: "red",
								});
							});
					});
				});
			})
			.catch((e) => {
				console.error("Document Template: failed to load manageable templates", e);
				this._loading_manage = false;
				frappe.show_alert({
					message: __("Failed to load templates for {0}.", [__(this.frm.doctype)]),
					indicator: "red",
				});
			});
	}

	_render_manage_list($wrap, all_templates) {
		$wrap.empty();

		if (!all_templates.length) {
			$wrap.html(`
				<div class="text-center text-muted py-4">
					<p class="mb-0">${__("No templates found.")}</p>
				</div>
			`);
			return;
		}

		const rows_html = all_templates
			.map((t, idx) => {
				const is_last = idx === all_templates.length - 1;

				return `
					<div class="d-flex align-items-center"
					     style="padding: 6px 0;${!is_last ? " border-bottom: 1px solid var(--border-color);" : ""}">
						<div class="flex-grow-1 ellipsis" style="min-width: 0"
						     title="${frappe.utils.escape_html(t.template_name)}">
							${frappe.utils.escape_html(t.template_name)}
						</div>
						<div class="d-flex align-items-center flex-shrink-0">
							<button class="btn btn-xs btn-default dt-overwrite ml-1"
							   data-name="${frappe.utils.escape_html(t.name)}"
							   data-label="${frappe.utils.escape_html(t.template_name)}"
							   title="${__("Replace with current form values")}">
							   ${__("Update")}
							</button>
							<a class="btn btn-xs btn-default ml-1"
							  href="${frappe.utils.get_form_link("Document Template", t.name)}"
							  title="${__("Open template")}"
							  aria-label="${__("Edit {0}", [frappe.utils.escape_html(t.template_name)])}">
							  ${frappe.utils.icon("edit", "xs")}
							</a>
							<button class="btn btn-xs btn-default dt-template-delete ml-1"
							   data-name="${frappe.utils.escape_html(t.name)}"
							   data-label="${frappe.utils.escape_html(t.template_name)}"
							   title="${__("Delete template")}"
							   aria-label="${__("Delete {0}", [frappe.utils.escape_html(t.template_name)])}">
							   ${frappe.utils.icon("trash", "xs")}
							</button>
						</div>
					</div>
				`;
			})
			.join("");

		$wrap.html(rows_html);
	}

	_apply_template(name, label) {
		const safe_label = frappe.utils.escape_html(label);
		frappe
			.call({
				method: "frappe.desk.doctype.document_template.document_template.get_template_data",
				args: { name },
			})
			.then(({ message }) => {
				if (!message) {
					frappe.show_alert({
						message: __("Template data not found."),
						indicator: "orange",
					});
					return;
				}

				let doc;
				try {
					doc = JSON.parse(message);
				} catch (e) {
					console.error("Document Template: failed to parse template data", e);
					frappe.show_alert({
						message: __("Failed to read template data. It may be corrupted."),
						indicator: "red",
					});
					return;
				}

				if (this.frm.doc.__islocal) {
					this._apply_to_form(doc, safe_label);
				} else {
					frappe.confirm(
						__(
							"Apply template {0}? Existing field values and child table rows will be replaced.",
							[safe_label.bold()]
						),
						() => this._apply_to_form(doc, safe_label)
					);
				}
			})
			.catch((e) => {
				console.error("Document Template: failed to load template", e);
				frappe.show_alert({
					message: __("Failed to load template {0}.", [safe_label]),
					indicator: "red",
				});
			});
	}

	_apply_to_form(doc, label) {
		const frm = this.frm;

		if (doc.doctype && doc.doctype !== frm.doctype) {
			console.warn(
				"Document Template: doctype mismatch — template is for",
				doc.doctype,
				"but form is",
				frm.doctype
			);
		}

		const scalar_fields = [];

		for (const df of frappe.meta.get_docfields(frm.doctype)) {
			if (cint(df.no_copy)) continue;
			if (frappe.model.no_value_type.includes(df.fieldtype)) continue;
			if (!(df.fieldname in doc)) continue;

			if (frappe.model.table_fields.includes(df.fieldtype)) {
				frm.clear_table(df.fieldname);
				for (const src_row of doc[df.fieldname] || []) {
					const new_row = frm.add_child(df.fieldname);
					for (const cdf of frappe.meta.get_docfields(df.options)) {
						if (!cint(cdf.no_copy) && cdf.fieldname in src_row) {
							new_row[cdf.fieldname] = src_row[cdf.fieldname];
						}
					}
				}
				frm.refresh_field(df.fieldname);
			} else {
				frm.doc[df.fieldname] = doc[df.fieldname];
				scalar_fields.push(df.fieldname);
			}
		}

		if (scalar_fields.length) {
			frm.refresh_fields(scalar_fields);
		}

		frm.dirty();

		frappe.show_alert({
			message: label ? __("Template {0} applied.", [label]) : __("Template applied."),
			indicator: "green",
		});
	}
};
