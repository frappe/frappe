// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

/**
 * Document Template manager for form toolbar.
 * For new (unsaved) documents — a "Templates" button opens the manage dialog.
 * For saved documents — "Templates" is added to the three-dot (⋮) menu.
 * At the bottom of the dialog, users can save the current form as a new template.
 */
frappe.ui.form.DocumentTemplate = class DocumentTemplate {
	constructor({ frm, page }) {
		this.frm = frm;
		this.page = page;
		this.$btn = null;
	}

	_is_own(template) {
		return template.owner === frappe.session.user;
	}

	_is_system_manager() {
		return frappe.user_roles.includes("System Manager");
	}

	_is_template_manager() {
		return frappe.user_roles.includes("Template Manager");
	}

	_should_include_field(df) {
		return !(cint(df.no_copy) || cint(df.read_only) || cint(df.hidden));
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
		this._manage_start = 0;
		this._manage_dialog = new frappe.ui.Dialog({
			title: __("Templates"),
			size: "medium",
		});

		let $body = this._manage_dialog.$body;

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

		let $save_row_wrapper = $("<div>").appendTo($body);
		let $save_row_inner = $('<div class="dt-save-row">').appendTo($save_row_wrapper);
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
		let $wrap = this._$manage_wrap;

		frappe
			.xcall("frappe.desk.doctype.document_template.document_template.get_templates", {
				reference_doctype: this.frm.doctype,
				limit_start: this._manage_start,
				limit_page_length: 10,
			})
			.then((data) => {
				data = data || {};
				this._render_manage_list(
					$wrap,
					data.templates || [],
					data.has_next_page || false,
					data.total || 0
				);
			});
	}

	_bind_manage_events() {
		let $wrap = this._$manage_wrap;

		$wrap.on("click.dtmanage", ".dt-row--active", (e) => {
			if ($(e.target).closest(".dt-manage-row-actions").length) return;

			let frm = this.frm;
			if (frm.doc.docstatus >= 1) {
				frappe.show_alert({
					message: __("Cannot apply template to a submitted document."),
					indicator: "orange",
				});
				return;
			}

			let $row = $(e.currentTarget);
			let name = $row.attr("data-name");
			let label = $row.attr("data-label") || "";

			if (frm.doc.__islocal) {
				this._apply_template(name, label);
				this._manage_dialog.hide();
			} else {
				frappe.confirm(
					__("Apply template {0}? This will modify the current document.", [label]),
					() => {
						this._apply_template(name, label);
						this._manage_dialog.hide();
					}
				);
			}
		});

		$wrap.on("click.dtmanage", ".dt-action-update", (e) => {
			e.preventDefault();
			e.stopPropagation();
			let $btn = $(e.currentTarget);
			let name = $btn.attr("data-name");
			let label = $btn.attr("data-label") || "";

			frappe.confirm(
				__("Replace template {0} with the current form values? This cannot be undone.", [
					label,
				]),
				() => {
					let data = this._capture_template_data();
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
								message: __("Template {0} updated.", [label]),
								indicator: "green",
							});
							this._load_manage_page();
						})
						.catch(() =>
							frappe.show_alert({
								message: __("Failed to update template {0}.", [label]),
								indicator: "red",
							})
						);
				}
			);
		});

		$wrap.on("click.dtmanage", ".dt-action-delete", (e) => {
			e.preventDefault();
			e.stopPropagation();
			let $btn = $(e.currentTarget);
			let name = $btn.attr("data-name");
			let label = $btn.attr("data-label") || "";
			if (!name) return;

			frappe.confirm(__("Delete template {0}?", [label]), () => {
				frappe.db
					.delete_doc("Document Template", name)
					.then(() => {
						frappe.show_alert({
							message: __("Template {0} deleted.", [label]),
							indicator: "green",
						});
						this._load_manage_page();
					})
					.catch(() =>
						frappe.show_alert({
							message: __("Failed to delete template {0}.", [label]),
							indicator: "red",
						})
					);
			});
		});

		$wrap.on("click.dtmanage", ".dt-page-prev", () => {
			if (this._manage_start > 0) {
				this._manage_start = Math.max(0, this._manage_start - 10);
				this._load_manage_page();
			}
		});

		$wrap.on("click.dtmanage", ".dt-page-next", () => {
			this._manage_start += 10;
			this._load_manage_page();
		});

		this._$save_row.on("click", ".dt-save-btn", () => this._save_new_template());
	}

	_save_new_template() {
		let name_val = (this._template_name_control.get_value() || "").trim();
		let is_private = this._private_check.get_value() ? 1 : 0;

		if (!name_val) {
			frappe.show_alert({
				message: __("Please enter a template name."),
				indicator: "orange",
			});
			this._template_name_control.$input?.focus();
			return;
		}

		let captured = this._capture_template_data();
		if (!captured) {
			frappe.show_alert({
				message: __("No data to save. Change at least one field before saving."),
				indicator: "orange",
			});
			return;
		}

		let $btn = this._$save_row.find(".dt-save-btn");
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
					message: __("Template {0} saved.", [name_val]),
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

	_render_manage_list($wrap, templates, has_next_page, total) {
		$wrap.empty();

		if (!templates.length) {
			$wrap.append(
				$('<p class="text-muted text-center mb-0">').text(
					__("No saved templates. Try saving the current form as a template.")
				)
			);
		}

		let showed_disabled_header = false;
		for (let t of templates) {
			if (t.disabled && !showed_disabled_header) {
				showed_disabled_header = true;
				$wrap.append(
					$('<div class="dt-disabled-separator text-muted text-small"></div>').text(
						__("Disabled")
					)
				);
			}
			$wrap.append(this._build_row(t));
		}

		if (total > 0 && (this._manage_start > 0 || has_next_page)) {
			let $pager = $('<div class="dt-pagination">');

			let $prev = $('<button class="btn btn-secondary btn-xs dt-page-prev">')
				.html(frappe.utils.icon("left", "xs"))
				.attr("title", __("Previous"))
				.prop("disabled", this._manage_start <= 0);

			let $next = $('<button class="btn btn-secondary btn-xs dt-page-next">')
				.html(frappe.utils.icon("right", "xs"))
				.attr("title", __("Next"))
				.prop("disabled", !has_next_page);

			let current_page = Math.floor(this._manage_start / 10) + 1;
			let $info = $('<span class="text-muted text-small dt-page-info">').text(
				__("Page {0}", [current_page])
			);

			$pager.append($prev, $info, $next);
			$wrap.append($pager);
		}
	}

	_build_row(template) {
		let is_own = this._is_own(template);
		let is_system_manager = this._is_system_manager();

		let row_cls = "dt-manage-row";
		if (!template.disabled) row_cls += " dt-row--active";
		if (template.disabled) row_cls += " dt-manage-row--disabled";

		let $row = $(`<div class="${row_cls}"></div>`)
			.attr("data-name", template.name)
			.attr("data-label", template.template_name);

		let $label = $('<div class="dt-manage-row-label ellipsis"></div>')
			.attr("title", template.template_name)
			.text(template.template_name);
		if (template.disabled) {
			$label.addClass("text-muted");
		}
		let $lock = null;
		if (template.private) {
			$lock = $('<div class="dt-manage-row-lock text-muted"></div>')
				.html(frappe.utils.icon("lock", "xs"))
				.attr("title", __("Private"));
		}

		let $actions = $('<div class="dt-manage-row-actions"></div>');

		let is_template_manager = this._is_template_manager();
		let can_manage = is_own || is_system_manager || (is_template_manager && !template.private);

		if (template.disabled) {
			if (can_manage) {
				this._add_edit_btn($actions, template);
				this._add_delete_btn($actions, template);
			}
		} else if (can_manage) {
			this._add_update_btn($actions, template);
			this._add_edit_btn($actions, template);
			this._add_delete_btn($actions, template);
		}

		let $label_group = $('<div class="dt-manage-row-label-group"></div>');
		$label_group.append($label);
		if ($lock) $label_group.append($lock);
		$row.append($label_group);
		$row.append($actions);
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
			.on("click", (e) => {
				e.preventDefault();
				e.stopPropagation();
				window.open(frappe.utils.get_form_link("Document Template", t.name), "_blank");
			})
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
			if (!doc || !doc.data) {
				frappe.show_alert({
					message: __("Template data not found."),
					indicator: "orange",
				});
				return;
			}
			this._apply_to_form(JSON.parse(doc.data), label);
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
						if (!this._should_include_field(cdf)) continue;
						if (!(cdf.fieldname in src_row)) continue;
						row_data[cdf.fieldname] = src_row[cdf.fieldname];
					}
					if (Object.keys(row_data).length) child_rows.push(row_data);
				}
				if (child_rows.length) field_updates[df.fieldname] = child_rows;
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

	_capture_template_data() {
		let copied = frappe.model.copy_doc(this.frm.doc);
		let result = {};

		for (let df of frappe.meta.get_docfields(copied.doctype)) {
			if (!this._should_include_field(df)) continue;
			let value = copied[df.fieldname];

			if (frappe.model.table_fields.includes(df.fieldtype)) {
				let rows = (value || [])
					.map((row) => {
						let clean = {};
						for (let cdf of frappe.meta.get_docfields(df.options)) {
							if (!this._should_include_field(cdf)) continue;
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
};
