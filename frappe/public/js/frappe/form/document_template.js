// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

/**
 * Document Template manager for the form toolbar.
 *
 * - For new (unsaved) documents a "Templates" button is added next to the
 *   primary action and opens the manage dialog.
 * - For saved documents "Templates" is appended to the three-dot (⋮) menu.
 *
 * The manage dialog lists templates accessible to the user (server-side
 * filtered) and lets them save the current form values as a new template.
 *
 * Per-row actions (update / edit / delete) are gated by client-side
 * permission checks via ``frappe.perm.has_perm`` which honours role-level
 * permissions on Document Template and the ``if_owner`` flag, mirroring the
 * server-side rules without hard-coding any role names.
 */
frappe.ui.form.DocumentTemplate = class DocumentTemplate {
	static PAGE_LENGTH = 10;

	constructor({ frm, page }) {
		this.frm = frm;
		this.page = page;
		this.$btn = null;
	}

	setup_buttons() {
		if (!this.$btn) {
			this.$btn = $('<button class="btn btn-default btn-sm hide">')
				.text(__("Templates"))
				.on("click", () => this.show_manage_dialog())
				.insertBefore(this.page.btn_primary);
		}
		this.$btn.toggleClass("hide", !this.frm.doc.__islocal);
	}

	add_template_menu_item() {
		if (this.frm.doc.__islocal) return;
		this.page.add_menu_item(__("Templates"), () => this.show_manage_dialog(), true);
	}

	show_manage_dialog() {
		if (this._manage_dialog) {
			this._manage_dialog.show();
			return;
		}

		this._manage_start = 0;
		this._manage_dialog = new frappe.ui.Dialog({
			title: __("Templates"),
			size: "medium",
		});

		const $body = this._manage_dialog.$body;

		this._$manage_wrap = $('<div class="dt-template-list">').appendTo($body);

		$('<div class="dt-section-break">')
			.append($("<hr>"))
			.append($('<div class="dt-section-heading">').text(__("Save as Template")))
			.appendTo($body);

		this._template_name_control = frappe.ui.form.make_control({
			df: {
				fieldtype: "Data",
				fieldname: "template_name",
				label: __("Template Name"),
			},
			parent: $body,
			render_input: true,
		});

		const $save_row_wrapper = $("<div>").appendTo($body);
		const $save_row_inner = $('<div class="dt-save-row">').appendTo($save_row_wrapper);
		this._$save_row = $save_row_wrapper;

		this._private_check = frappe.ui.form.make_control({
			df: {
				fieldtype: "Check",
				fieldname: "dt_private",
				label: __("Private"),
			},
			parent: $save_row_inner,
			render_input: true,
		});

		$('<button class="btn btn-sm btn-primary dt-save-btn">')
			.text(__("Save"))
			.appendTo($save_row_inner);

		this._bind_manage_events();
		this._load_manage_page();
		this._manage_dialog.show();
	}

	_load_manage_page() {
		frappe.model.with_doctype("Document Template", () => {
			frappe
				.xcall("frappe.desk.doctype.document_template.document_template.get_templates", {
					reference_doctype: this.frm.doctype,
					limit_start: this._manage_start,
					limit_page_length: DocumentTemplate.PAGE_LENGTH,
				})
				.then((data) => {
					data = data || {};
					this._render_manage_list(
						this._$manage_wrap,
						data.templates || [],
						!!data.has_next_page
					);
				});
		});
	}

	_bind_manage_events() {
		const $wrap = this._$manage_wrap;

		$wrap.on("click.dtmanage", ".dt-row--active", (e) => this._on_row_click(e));
		$wrap.on("click.dtmanage", ".dt-action-update", (e) => this._on_update_click(e));
		$wrap.on("click.dtmanage", ".dt-action-edit", (e) => this._on_edit_click(e));
		$wrap.on("click.dtmanage", ".dt-action-delete", (e) => this._on_delete_click(e));
		$wrap.on("click.dtmanage", ".dt-page-prev", () => this._on_page_prev());
		$wrap.on("click.dtmanage", ".dt-page-next", () => this._on_page_next());

		this._$save_row.on("click", ".dt-save-btn", () => this._save_new_template());
	}

	_on_row_click(e) {
		if ($(e.target).closest(".dt-manage-row-actions").length) return;

		const frm = this.frm;
		if (frm.doc.docstatus >= 1) {
			frappe.show_alert({
				message: __("Cannot apply template to a submitted document"),
				indicator: "orange",
			});
			return;
		}

		const $row = $(e.currentTarget);
		const name = $row.attr("data-name");
		const label = $row.attr("data-label") || "";

		if (frm.doc.__islocal) {
			this._apply_template(name, label);
			this._manage_dialog.hide();
		} else {
			frappe.confirm(
				__("Apply template {0}? This will modify the current document", [label]),
				() => {
					this._apply_template(name, label);
					this._manage_dialog.hide();
				}
			);
		}
	}

	_on_update_click(e) {
		e.preventDefault();
		e.stopPropagation();
		const $btn = $(e.currentTarget);
		const name = $btn.attr("data-name");
		const label = $btn.attr("data-label") || "";

		frappe.confirm(
			__("Replace template {0} with the current form values? This cannot be undone", [
				label,
			]),
			() => {
				const data = this._capture_template_data();
				if (!data) {
					frappe.show_alert({
						message: __("No data to save. Change at least one field first."),
						indicator: "orange",
					});
					return;
				}
				frappe.db
					.set_value("Document Template", name, "data", JSON.stringify(data))
					.then(() => {
						frappe.show_alert({
							message: __("Template {0} updated", [label]),
							indicator: "green",
						});
						this._load_manage_page();
					})
					.catch(() =>
						frappe.show_alert({
							message: __("Failed to update template {0}", [label]),
							indicator: "red",
						})
					);
			}
		);
	}

	_on_edit_click(e) {
		e.preventDefault();
		e.stopPropagation();
		const name = $(e.currentTarget).attr("data-name");
		if (!name) return;
		window.open(frappe.utils.get_form_link("Document Template", name), "_blank");
	}

	_on_delete_click(e) {
		e.preventDefault();
		e.stopPropagation();
		const $btn = $(e.currentTarget);
		const name = $btn.attr("data-name");
		const label = $btn.attr("data-label") || "";
		if (!name) return;

		frappe.confirm(__("Delete template {0}?", [label]), () => {
			frappe.db
				.delete_doc("Document Template", name)
				.then(() => {
					frappe.show_alert({
						message: __("Template {0} deleted", [label]),
						indicator: "green",
					});
					this._load_manage_page();
				})
				.catch(() =>
					frappe.show_alert({
						message: __("Failed to delete template {0}", [label]),
						indicator: "red",
					})
				);
		});
	}

	_on_page_prev() {
		if (this._manage_start > 0) {
			this._manage_start = Math.max(0, this._manage_start - DocumentTemplate.PAGE_LENGTH);
			this._load_manage_page();
		}
	}

	_on_page_next() {
		this._manage_start += DocumentTemplate.PAGE_LENGTH;
		this._load_manage_page();
	}

	_save_new_template() {
		const name_val = this._template_name_control.get_value().trim();
		const is_private = this._private_check.get_value() ? 1 : 0;

		if (!name_val) {
			frappe.show_alert({
				message: __("Please enter a template name."),
				indicator: "orange",
			});
			this._template_name_control.$input?.focus();
			return;
		}

		const captured = this._capture_template_data();
		if (!captured) {
			frappe.show_alert({
				message: __("No data to save. Change at least one field before saving."),
				indicator: "orange",
			});
			return;
		}

		const $btn = this._$save_row.find(".dt-save-btn");
		$btn.prop("disabled", true);

		frappe.db
			.insert({
				doctype: "Document Template",
				reference_doctype: this.frm.doctype,
				template_name: name_val,
				private: is_private,
				data: JSON.stringify(captured),
			})
			.then(() => {
				frappe.show_alert({
					message: __("Template {0} saved", [name_val]),
					indicator: "green",
				});
				this._template_name_control.set_value("");
				this._private_check.set_value(0);
				this._load_manage_page();
			})
			.catch((e) => {
				console.error("Document Template: failed to save template", e);
				frappe.show_alert({
					message: __("Failed to save template."),
					indicator: "red",
				});
			})
			.finally(() => $btn.prop("disabled", false));
	}

	_capture_template_data() {
		const copied = frappe.model.copy_doc(this.frm.doc, false);
		const result = {};

		for (const df of frappe.meta.get_docfields(copied.doctype)) {
			const value = copied[df.fieldname];

			if (frappe.model.table_fields.includes(df.fieldtype)) {
				const rows = (value || [])
					.map((row) => {
						const clean = {};
						for (const cdf of frappe.meta.get_docfields(df.options)) {
							if (
								row[cdf.fieldname] != null &&
								row[cdf.fieldname] !== "" &&
								row[cdf.fieldname] != cdf.__default_value
							) {
								clean[cdf.fieldname] = row[cdf.fieldname];
							}
						}
						return clean;
					})
					.filter((r) => Object.keys(r).length);

				if (rows.length) result[df.fieldname] = rows;
				continue;
			}

			if (value != null && value !== "" && value != df.__default_value) {
				result[df.fieldname] = value;
			}
		}

		return Object.keys(result).length ? result : null;
	}

	_render_manage_list($wrap, templates, has_next_page) {
		$wrap.empty();

		if (!templates.length && this._manage_start === 0) {
			$wrap.append(
				$('<p class="text-muted text-center dt-no-saved-templates">').text(
					__("No saved templates. Try saving the current form as a template.")
				)
			);
		}

		let showed_disabled_header = false;
		let has_active_templates = false;
		for (const t of templates) {
			if (t.disabled && !showed_disabled_header) {
				showed_disabled_header = true;
				if (has_active_templates) {
					$wrap.append($('<hr class="dt-disabled-separator-hr">'));
				}
				$wrap.append(
					$('<div class="dt-disabled-separator text-muted text-small"></div>').text(
						__("Disabled")
					)
				);
			}
			if (!t.disabled) has_active_templates = true;
			$wrap.append(this._build_row(t));
		}

		if (this._manage_start > 0 || has_next_page) {
			const $pager = $('<div class="dt-pagination">');

			const $prev = $('<button class="btn btn-secondary btn-xs dt-page-prev">')
				.html(frappe.utils.icon("left", "xs"))
				.attr("title", __("Previous"))
				.prop("disabled", this._manage_start <= 0);

			const $next = $('<button class="btn btn-secondary btn-xs dt-page-next">')
				.html(frappe.utils.icon("right", "xs"))
				.attr("title", __("Next"))
				.prop("disabled", !has_next_page);

			const current_page = Math.floor(this._manage_start / DocumentTemplate.PAGE_LENGTH) + 1;
			const $info = $('<span class="text-muted text-small dt-page-info">').text(
				__("Page {0}", [current_page])
			);

			$pager.append($prev, $info, $next);
			$wrap.append($pager);
		}
	}

	_build_row(template) {
		let row_cls = "dt-manage-row";
		if (!template.disabled) row_cls += " dt-row--active";

		const $row = $(`<div class="${row_cls}"></div>`)
			.attr("data-name", template.name)
			.attr("data-label", template.template_name);

		const $label = $('<div class="dt-manage-row-label ellipsis"></div>')
			.attr("title", template.template_name)
			.text(template.template_name);
		if (template.disabled) $label.addClass("text-muted");

		const $label_group = $('<div class="dt-manage-row-label-group"></div>').append($label);
		if (template.private) {
			$label_group.append(
				$('<div class="dt-manage-row-lock text-muted"></div>').html(
					frappe.utils.icon("lock", "xs")
				)
			);
		}

		const $actions = $('<div class="dt-manage-row-actions"></div>');
		const perm_doc = {
			doctype: "Document Template",
			name: template.name,
			owner: template.owner,
		};
		const can_write = frappe.perm.has_perm("Document Template", 0, "write", perm_doc);

		if (!template.disabled && can_write) {
			this._add_update_btn($actions, template);
			this._add_edit_btn($actions, template);
			this._add_delete_btn($actions, template);
		}

		$row.append($label_group).append($actions);
		return $row;
	}

	_add_update_btn($actions, t) {
		$('<button class="btn btn-xs btn-default dt-action-update" type="button"></button>')
			.attr("data-name", t.name)
			.attr("data-label", t.template_name)
			.text(__("Update"))
			.attr("title", __("Replace with current form values"))
			.appendTo($actions);
	}

	_add_edit_btn($actions, t) {
		$('<button class="btn btn-xs btn-default dt-action-edit" type="button"></button>')
			.attr("data-name", t.name)
			.attr("title", __("Open template"))
			.attr("aria-label", __("Edit {0}", [t.template_name]))
			.html(frappe.utils.icon("edit", "xs"))
			.appendTo($actions);
	}

	_add_delete_btn($actions, t) {
		$('<button class="btn btn-xs btn-default dt-action-delete" type="button"></button>')
			.attr("data-name", t.name)
			.attr("data-label", t.template_name)
			.attr("title", __("Delete template"))
			.attr("aria-label", __("Delete {0}", [t.template_name]))
			.html(frappe.utils.icon("trash", "xs"))
			.appendTo($actions);
	}

	_apply_template(name, label) {
		frappe.db.get_doc("Document Template", name).then((doc) => {
			if (!doc) {
				frappe.show_alert({
					message: __("Template not found."),
					indicator: "orange",
				});
				return;
			}
			this._apply_to_form(JSON.parse(doc.data), label);
		});
	}

	async _apply_to_form(doc, label) {
		const frm = this.frm;

		if (Object.keys(doc).length) {
			await frm.set_value(doc);
		}

		frm.dirty();
		frappe.show_alert({
			message: label ? __("Template {0} applied", [label]) : __("Template applied"),
			indicator: "green",
		});
	}
};
