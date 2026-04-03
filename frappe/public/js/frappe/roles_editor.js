frappe.RoleEditor = class {
	/**
	 * Create a role editor for a form child table.
	 *
	 * @param {HTMLElement|JQuery} wrapper Container for the MultiCheck control.
	 * @param {frappe.ui.form.Form} frm Form whose role rows are edited.
	 * @param {boolean|number|Object} [disable=false] Disable role selection inputs, or pass role row configuration as the third argument.
	 * @param {Object} [options] Role row configuration overrides.
	 * @param {string} [options.table_fieldname="roles"] Child table field containing role rows.
	 * @param {string} [options.role_fieldname="role"] Field in each child row that stores the role value.
	 * @param {string} [options.child_doctype] Child DocType used when adding role rows. Defaults to the table field's configured child DocType or "Has Role".
	 */
	constructor(wrapper, frm, disable = false, options = {}) {
		if (disable && typeof disable === "object") {
			options = disable;
			disable = false;
		}

		const { table_fieldname = "roles", role_fieldname = "role", child_doctype } = options;
		const configured_child_doctype = frappe.meta.get_docfield(
			frm.doctype,
			table_fieldname
		)?.options;

		this.frm = frm;
		this.wrapper = wrapper;
		this.disable = Boolean(disable);
		this.table_fieldname = table_fieldname;
		this.role_fieldname = role_fieldname;
		this.child_doctype = child_doctype || configured_child_doctype || "Has Role";
		let user_roles = this.get_selected_roles();
		this.multicheck = frappe.ui.form.make_control({
			parent: wrapper,
			df: {
				fieldname: this.table_fieldname,
				fieldtype: "MultiCheck",
				select_all: true,
				columns: "15rem",
				get_data: () => {
					return frappe
						.xcall("frappe.core.doctype.user.user.get_all_roles")
						.then((roles) => {
							return roles.map((role) => {
								return {
									label: __(role),
									value: role,
									checked: user_roles.includes(role),
								};
							});
						});
				},
				on_change: () => {
					this.set_roles_in_table();
					this.frm.dirty();
				},
			},
			render_input: true,
		});

		let original_func = this.multicheck.make_checkboxes;
		this.multicheck.make_checkboxes = () => {
			original_func.call(this.multicheck);
			this.multicheck.$wrapper.find(".label-area").click((e) => {
				let role = $(e.target).data("unit");
				role && this.show_permissions(role);
				e.preventDefault();
			});
			this.set_enable_disable();
		};
	}
	set_enable_disable() {
		$(this.wrapper)
			.find('input[type="checkbox"]')
			.attr("disabled", this.disable ? true : false);
		$(this.wrapper)
			.find("button")
			.attr("disabled", this.disable ? true : false);
	}
	show_permissions(role) {
		// show permissions for a role
		if (!this.perm_dialog) {
			this.make_perm_dialog();
		}
		$(this.perm_dialog.body).empty();
		let is_dark = document.documentElement.getAttribute("data-theme") === "dark";
		let header_bg_color = is_dark ? "bg-dark text-white" : "bg-light";
		return frappe
			.xcall("frappe.core.doctype.user.user.get_perm_info", { role })
			.then((permissions) => {
				const $body = $(this.perm_dialog.body);
				if (!permissions.length) {
					$body.append(`<div class="text-muted text-center padding">
						${__("{0} role does not have permission on any doctype", [__(role)])}
					</div>`);
				} else {
					$body.append(`
						<div style="max-height:calc(100vh - 200px); overflow-y:auto;">
							<table class="user-perm">
								<thead>
									<tr>
										<th class="sticky-top ${header_bg_color}"> ${__("Document Type")} </th>
										<th class="sticky-top ${header_bg_color}"> ${__("Level")} </th>
										<th class="sticky-top ${header_bg_color}"> ${__("If Owner")} </th>
										${frappe.perm.rights
											.map(
												(p) =>
													`<th class="sticky-top ${header_bg_color}">${__(
														frappe.unscrub(p)
													)}</th>`
											)
											.join("")}
									</tr>
								</thead>
								<tbody></tbody>
							</table>
						</div>
					`);
					permissions.forEach((perm) => {
						$body.find("tbody").append(`
							<tr>
								<td>${__(perm.parent)}</td>
								<td>${perm.permlevel}</td>
								<td>${perm.if_owner ? frappe.utils.icon("check", "xs") : "-"}</td>
								${frappe.perm.rights
									.map(
										(p) =>
											`<td class="text-muted bold">${
												perm[p] ? frappe.utils.icon("check", "xs") : "-"
											}</td>`
									)
									.join("")}
							</tr>
						`);
					});
				}
				this.perm_dialog.set_title(__(role));
				this.perm_dialog.show();
			});
	}
	make_perm_dialog() {
		this.perm_dialog = new frappe.ui.Dialog({
			title: __("Role Permissions"),
		});

		this.perm_dialog.$wrapper
			.find(".modal-dialog")
			.css("width", "auto")
			.css("max-width", "1200px");

		this.perm_dialog.$wrapper.find(".modal-body").css("overflow", "overlay");
	}
	show() {
		this.reset();
		this.set_enable_disable();
	}

	reset() {
		let user_roles = this.get_selected_roles();
		this.multicheck.selected_options = user_roles;
		this.multicheck.refresh_input();
	}
	set_roles_in_table() {
		let roles = this.get_role_rows();
		let checked_options = this.multicheck.get_checked_options();
		roles.forEach((role_doc) => {
			if (!checked_options.includes(this.get_role_value(role_doc))) {
				frappe.model.clear_doc(role_doc.doctype, role_doc.name);
			}
		});
		checked_options.forEach((role) => {
			if (!roles.find((d) => this.get_role_value(d) === role)) {
				let role_doc = frappe.model.add_child(
					this.frm.doc,
					this.child_doctype,
					this.table_fieldname
				);
				this.set_role_value(role_doc, role);
			}
		});
	}
	get_role_rows() {
		return this.frm.doc[this.table_fieldname] || [];
	}
	get_selected_roles() {
		return this.get_role_rows().map((row) => this.get_role_value(row));
	}
	get_role_value(row) {
		return row[this.role_fieldname];
	}
	set_role_value(row, role) {
		row[this.role_fieldname] = role;
	}
	get_roles() {
		return {
			checked_roles: this.multicheck.get_checked_options(),
			unchecked_roles: this.multicheck.get_unchecked_options(),
		};
	}
};
