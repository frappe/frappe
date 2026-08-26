// Copyright (c) 2026, Frappe Technologies and contributors
// For license information, please see license.txt

/**
 * Document Template manager for the form toolbar.
 *
 * - For new (unsaved) documents a "Templates" button is added next to the
 *   primary action and opens the manage dialog.
 * - For saved documents "Templates" is appended to the three-dot menu.
 *
 * The manage dialog lists templates accessible to the user (server-side
 * filtered) and lets them save the current form values as a new template.
 *
 * Per-row actions (update / edit / delete) are gated by client-side
 * permission checks via ``frappe.perm.has_perm`` which honours role-level
 * permissions on Document Template and the ``if_owner`` flag, mirroring the
 * server-side rules without hard-coding any role names.
 */
frappe.ui.form.TemplateManager = class TemplateManager {
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

	add_menu_item() {
		if (this.frm.doc.__islocal) return;
		this.page.add_menu_item(__("Templates"), () => this.show_manage_dialog(), true);
	}

	async show_manage_dialog() {
		if (this._manage_dialog) {
			this._manage_dialog.show();
			return;
		}

		this._manage_start = 0;

		const data = await this._fetch_templates();

		this._manage_dialog = new frappe.ui.Dialog({
			title: __("Templates"),
			size: "medium",
		});

		const $body = this._manage_dialog.$body;

		this._$manage_wrap = $('<div class="dt-template-list">').appendTo($body);

		$body.append(
			`<div class="dt-section-break"><hr><div class="dt-section-heading">${__(
				"Save as Template"
			)}</div></div>`
		);

		this._template_name_control = frappe.ui.form.make_control({
			df: {
				fieldtype: "Data",
				fieldname: "template_name",
				label: __("Template Name"),
			},
			parent: $body,
			render_input: true,
		});

		const $save_row = $('<div class="dt-save-row">').appendTo($body);

		this._private_check = frappe.ui.form.make_control({
			df: {
				fieldtype: "Check",
				fieldname: "dt_private",
				label: __("Private"),
			},
			parent: $save_row,
			render_input: true,
		});

		this._save_btn_control = frappe.ui.form.make_control({
			df: {
				fieldtype: "Button",
				fieldname: "dt_save",
				label: __("Save"),
			},
			parent: $save_row,
			render_input: true,
		});
		this._save_btn_control.$input
			.addClass("btn-primary dt-save-btn")
			.removeClass("btn-default");

		this._bind_manage_events();
		this._render_manage_list(this._$manage_wrap, data.templates || [], data.has_next_page);
		this._manage_dialog.show();
	}

	_fetch_templates() {
		const args = {
			reference_doctype: this.frm.doctype,
			limit_start: this._manage_start,
			limit_page_length: TemplateManager.PAGE_LENGTH,
		};
		// Only request meta if we don't already have it cached client-side.
		if (!frappe.get_meta("Document Template")) {
			args.with_meta = true;
		}
		return frappe.xcall(
			"frappe.desk.doctype.document_template.document_template.get_templates",
			args
		);
	}

	_load_manage_page() {
		this._fetch_templates().then((data) => {
			this._render_manage_list(this._$manage_wrap, data.templates || [], data.has_next_page);
		});
	}

	_bind_manage_events() {
		const $wrap = this._$manage_wrap;

		$wrap.on("click.dtmanage", ".dt-manage-row", (e) => {
			const row = e.currentTarget;
			const name = row.getAttribute("data-name");
			const label = row.getAttribute("data-label") || "";
			const action_btn = e.target.closest(
				".dt-action-update, .dt-action-edit, .dt-action-delete"
			);

			if (!action_btn) {
				if (row.classList.contains("dt-row--active")) {
					this._on_row_click(name, label);
				}
				return;
			}

			e.preventDefault();
			e.stopPropagation();
			if (action_btn.classList.contains("dt-action-update")) {
				this._on_update_click(name, label);
			} else if (action_btn.classList.contains("dt-action-edit")) {
				this._on_edit_click(name);
			} else if (action_btn.classList.contains("dt-action-delete")) {
				this._on_delete_click(name, label);
			}
		});
		$wrap.on("click.dtmanage", ".dt-page-prev", () => this._on_page_prev());
		$wrap.on("click.dtmanage", ".dt-page-next", () => this._on_page_next());

		this._save_btn_control.$input.on("click", () => this._save_new_template());
	}

	_confirm(message) {
		return new Promise((resolve) =>
			frappe.confirm(
				message,
				() => resolve(true),
				() => resolve(false)
			)
		);
	}

	async _on_row_click(name, label) {
		if (!this.frm.doc.__islocal) {
			const confirmed = await this._confirm(
				__("Apply template <strong>{0}</strong>? This will modify the current document.", [
					label,
				])
			);
			if (!confirmed) return;
		}

		this._apply_template(name, label);
		this._manage_dialog.hide();
	}

	async _on_update_click(name, label) {
		const confirmed = await this._confirm(
			__(
				"Replace template <strong>{0}</strong> with the current form values? This cannot be undone.",
				[label]
			)
		);
		if (!confirmed) return;

		const data = this._capture_template_data();
		if (!data) {
			frappe.show_alert({
				message: __("No data to save. Change at least one field first."),
				indicator: "orange",
			});
			return;
		}

		await frappe.db.set_value("Document Template", name, "data", JSON.stringify(data));
		frappe.show_alert({
			message: __("Template <strong>{0}</strong> updated", [label]),
			indicator: "green",
		});
	}

	_on_edit_click(name) {
		if (!name) return;
		window.open(frappe.utils.get_form_link("Document Template", name), "_blank");
	}

	async _on_delete_click(name, label) {
		if (!name) return;

		const confirmed = await this._confirm(
			__("Delete template <strong>{0}</strong>?", [label])
		);
		if (!confirmed) return;

		await frappe.db.delete_doc("Document Template", name);
		frappe.show_alert({
			message: __("Template <strong>{0}</strong> deleted", [label]),
			indicator: "green",
		});
		this._load_manage_page();
	}

	_on_page_prev() {
		if (this._manage_start > 0) {
			this._manage_start = Math.max(0, this._manage_start - TemplateManager.PAGE_LENGTH);
			this._load_manage_page();
		}
	}

	_on_page_next() {
		this._manage_start += TemplateManager.PAGE_LENGTH;
		this._load_manage_page();
	}

	_save_new_template() {
		const name_val = this._template_name_control.get_value().trim();
		const is_private = this._private_check.get_value() ? 1 : 0;

		if (!name_val) {
			frappe.show_alert({
				message: __("Please enter a template name"),
				indicator: "red",
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

		const $btn = this._save_btn_control.$input;
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
					message: __("Template <strong>{0}</strong> saved", [name_val]),
					indicator: "green",
				});
				this._template_name_control.set_value("");
				this._private_check.set_value(0);
				this._load_manage_page();
			})
			.finally(() => $btn.prop("disabled", false));
	}

	_capture_template_data() {
		const copied = frappe.model.copy_doc(this.frm.doc);
		const result = {};
		const should_copy = (value, df) =>
			!frappe.utils.is_empty(value) && value != df.__default_value;

		for (const df of frappe.meta.get_docfields(copied.doctype)) {
			const value = copied[df.fieldname];

			if (frappe.model.table_fields.includes(df.fieldtype)) {
				const rows = (value || [])
					.map((row) => {
						const clean = {};
						for (const cdf of frappe.meta.get_docfields(df.options)) {
							if (should_copy(row[cdf.fieldname], cdf)) {
								clean[cdf.fieldname] = row[cdf.fieldname];
							}
						}
						return clean;
					})
					.filter((r) => Object.keys(r).length);

				if (rows.length) result[df.fieldname] = rows;
				continue;
			}

			if (should_copy(value, df)) {
				result[df.fieldname] = value;
			}
		}

		return Object.keys(result).length ? result : null;
	}

	_render_manage_list($wrap, templates, has_next_page) {
		let html = "";

		if (!templates.length && this._manage_start === 0) {
			html += `<p class="text-muted text-center dt-no-saved-templates">${__(
				"No saved templates. Try saving the current form as a template."
			)}</p>`;
		}

		let showed_disabled_header = false;
		let has_active_templates = false;
		for (const t of templates) {
			if (t.disabled && !showed_disabled_header) {
				showed_disabled_header = true;
				if (has_active_templates) {
					html += '<hr class="dt-disabled-separator-hr">';
				}
				html += `<div class="dt-disabled-separator text-muted text-small">${__(
					"Disabled"
				)}</div>`;
			}
			if (!t.disabled) has_active_templates = true;
			html += this._build_row(t);
		}

		if (this._manage_start > 0 || has_next_page) {
			const current_page = Math.floor(this._manage_start / TemplateManager.PAGE_LENGTH) + 1;
			const prevDisabled = this._manage_start <= 0 ? "disabled" : "";
			const nextDisabled = !has_next_page ? "disabled" : "";
			html += `<div class="dt-pagination">
				<button class="btn btn-secondary btn-xs dt-page-prev" title="${__(
					"Previous"
				)}" ${prevDisabled}>${frappe.utils.icon("chevron-left", "xs")}</button>
				<span class="text-muted text-small dt-page-info">${__("Page {0}", [current_page])}</span>
				<button class="btn btn-secondary btn-xs dt-page-next" title="${__(
					"Next"
				)}" ${nextDisabled}>${frappe.utils.icon("chevron-right", "xs")}</button>
			</div>`;
		}

		$wrap.html(html);
	}

	_build_row(template) {
		const isActive = !template.disabled && this.frm.doc.docstatus < 1;
		const rowCls = `dt-manage-row${isActive ? " dt-row--active" : ""}`;
		const labelCls = `dt-manage-row-label ellipsis${template.disabled ? " text-muted" : ""}`;
		const lockHtml = template.private
			? `<div class="dt-manage-row-lock text-muted">${frappe.utils.icon("lock", "xs")}</div>`
			: "";

		const perm_doc = { doctype: "Document Template", ...template };
		const can_write = frappe.perm.has_perm("Document Template", 0, "write", perm_doc);
		const can_delete = frappe.perm.has_perm("Document Template", 0, "delete", perm_doc);

		const esc = frappe.utils.escape_html;
		const name = esc(template.name);
		const label = esc(template.template_name);

		let actionsHtml = "";
		if (can_write) {
			actionsHtml += `<button class="btn btn-default btn-xs dt-action-update" title="${esc(
				__("Replace with current form values")
			)}">${esc(__("Update"))}</button>`;
			actionsHtml += `<button class="btn btn-default btn-xs dt-action-edit" title="${esc(
				__("Open template")
			)}" aria-label="${esc(__("Edit {0}", [template.template_name]))}">${frappe.utils.icon(
				"pencil",
				"xs"
			)}</button>`;
		}
		if (can_delete) {
			actionsHtml += `<button class="btn btn-default btn-xs dt-action-delete" title="${esc(
				__("Delete template")
			)}" aria-label="${esc(
				__("Delete {0}", [template.template_name])
			)}">${frappe.utils.icon("trash", "xs")}</button>`;
		}

		return `<div class="${rowCls}" data-name="${name}" data-label="${label}">
			<div class="dt-manage-row-label-group">
				<div class="${labelCls}" title="${label}">${label}</div>${lockHtml}
			</div>
			<div class="dt-manage-row-actions">${actionsHtml}</div>
		</div>`;
	}

	async _apply_template(name, label) {
		const doc = await frappe.db.get_doc("Document Template", name);
		let template = doc?.data;
		if (!template) {
			frappe.show_alert({
				message: __("Template not found"),
				indicator: "orange",
			});
			return;
		}
		this._apply_to_form(JSON.parse(template), label);
	}

	async _apply_to_form(template, label) {
		const frm = this.frm;
		for (const key in template) {
			const df = frappe.meta.get_docfield(frm.doctype, key);
			if (!df) continue;

			if (frappe.model.table_fields.includes(df.fieldtype)) {
				frm.doc[key] = [];
				const children = template[key] || [];
				for (const child of children) {
					const new_child = frm.add_child(key);
					Object.assign(new_child, child);
				}
				continue;
			}

			frm.doc[key] = template[key];
		}
		frm.refresh_fields();
		frm.dirty();
		frappe.show_alert({
			message: label
				? __("Template <strong>{0}</strong> applied", [label])
				: __("Template applied"),
			indicator: "green",
		});
	}
};
