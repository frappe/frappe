frappe.pages["permission-manager"].on_page_load = (wrapper) => {
	let page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Role Permissions Manager"),
		card_layout: true,
		single_column: true,
	});

	frappe.breadcrumbs.add("Setup");

	$("<div class='perm-engine' style='min-height: 200px; padding: 15px;'></div>").appendTo(
		page.main
	);
	$(frappe.render_template("permission_manager_help", {})).appendTo(page.main);
	wrapper.permission_engine = new frappe.PermissionEngine(wrapper);
};

frappe.pages["permission-manager"].refresh = function (wrapper) {
	wrapper.permission_engine.set_from_route();
};

frappe.PermissionEngine = class PermissionEngine {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = wrapper.page;
		this.body = $(this.wrapper).find(".perm-engine");
		this.make();
		this.refresh();
		this.add_check_events();
	}

	make() {
		this.make_reset_button();
		frappe
			.call({
				module: "frappe.core",
				page: "permission_manager",
				method: "get_roles_and_doctypes",
			})
			.then((res) => {
				this.options = res.message;
				this.setup_page();
			});
	}

	setup_page() {
		this.doctype_select = this.wrapper.page.add_field({
			fieldname: "doctype_select",
			label: __("Document Type"),
			fieldtype: "Link",
			options: "DocType",
			change: function () {
				frappe.set_route("permission-manager", this.get_value());
			},
		});

		this.role_select = this.wrapper.page.add_field({
			fieldname: "role_select",
			label: __("Roles"),
			fieldtype: "Link",
			options: "Role",
			change: () => this.refresh(),
		});

		this.page.add_inner_button(__("Set User Permissions"), () => {
			return frappe.set_route("List", "User Permission");
		});
		this.set_from_route();
	}

	set_from_route() {
		if (!this.doctype_select) {
			// selects not yet loaded, call again after a bit
			setTimeout(() => {
				this.set_from_route();
			}, 500);
			return;
		}
		if (frappe.get_route()[1]) {
			this.doctype_select.set_value(frappe.get_route()[1]);
		} else if (frappe.route_options) {
			if (frappe.route_options.doctype) {
				this.doctype_select.set_value(frappe.route_options.doctype);
			}
			if (frappe.route_options.role) {
				this.role_select.set_value(frappe.route_options.role);
			}
			frappe.route_options = null;
		}
		this.refresh();
	}

	get_standard_permissions(callback) {
		let doctype = this.get_doctype();
		if (doctype) {
			return frappe.call({
				module: "frappe.core",
				page: "permission_manager",
				method: "get_standard_permissions",
				args: { doctype: doctype },
				callback: callback,
			});
		}
		return false;
	}

	reset_std_permissions(data) {
		let doctype = this.get_doctype();
		let d = frappe.confirm(__("Reset Permissions for {0}?", [doctype]), () => {
			return frappe
				.call({
					module: "frappe.core",
					page: "permission_manager",
					method: "reset",
					args: { doctype },
				})
				.then(() => {
					this.refresh();
				});
		});

		// show standard permissions
		let $d = $(d.wrapper)
			.find(".frappe-confirm-message")
			.append("<hr><h5>Standard Permissions:</h5><br>");
		let $wrapper = $("<p></p>").appendTo($d);
		data.message.forEach((d) => {
			let rights = this.rights
				.filter((r) => d[r])
				.map((r) => {
					return __(toTitle(frappe.unscrub(r)));
				});

			d.rights = rights.join(", ");

			$wrapper.append(`<div class="row">\
				<div class="col-xs-5"><b>${d.role}</b>, Level ${d.permlevel || 0}</div>\
				<div class="col-xs-7">${d.rights}</div>\
			</div><br>`);
		});
	}

	get_doctype() {
		return this.doctype_select.get_value();
	}

	get_role() {
		return this.role_select.get_value();
	}

	set_empty_message(message) {
		this.body.html(`
		<div class="text-muted flex justify-center align-center" style="min-height: 300px;">
			<p class='text-muted'>
				${message}
			</p>
		</div>`);
	}

	refresh() {
		this.page.clear_secondary_action();
		this.page.clear_primary_action();

		if (!this.doctype_select) {
			return this.set_empty_message(__("Loading"));
		}

		let doctype = this.get_doctype();
		let role = this.get_role();

		if (!doctype && !role) {
			return this.set_empty_message(__("Select Document Type or Role to start."));
		}

		// get permissions
		frappe
			.call({
				module: "frappe.core",
				page: "permission_manager",
				method: "get_permissions",
				args: { doctype, role },
			})
			.then((r) => {
				this.render(r.message);
			});
	}

	render(perm_list) {
		this.body.empty();
		this.perm_list = perm_list || [];
		if (!this.perm_list.length) {
			this.set_empty_message(__("No Permissions set for this criteria."));
		} else {
			this.show_permission_table(this.perm_list);
		}
		this.show_add_rule();
		this.get_doctype() && this.make_reset_button();
	}

	show_permission_table(perm_list) {
		this.table = $(
			"<div class='table-responsive'>\
			<table class='table table-borderless'>\
				<thead><tr></tr></thead>\
				<tbody></tbody>\
			</table>\
		</div>"
		).appendTo(this.body);

		const table_columns = [
			[__("Document Type"), 150],
			[__("Role"), 170],
			[__("Level"), 40],
			[__("Permissions"), 350],
			["", 40],
		];

		table_columns.forEach((col) => {
			$("<th>")
				.html(col[0])
				.css("width", col[1] + "px")
				.appendTo(this.table.find("thead tr"));
		});

		perm_list.forEach((d) => {
			if (d.parent === "DocType") {
				return;
			}

			if (!d.permlevel) d.permlevel = 0;

			let row = $("<tr>").appendTo(this.table.find("tbody"));
			this.add_cell(row, d, "parent");
			let role_cell = this.add_cell(row, d, "role");

			this.set_show_users(role_cell, d.role);

			if (d.permlevel === 0) {
				// this.setup_user_permissions(d, role_cell);
				this.setup_if_owner(d, role_cell);
			}

			let cell = this.add_cell(row, d, "permlevel");

			if (d.permlevel == 0) {
				cell.css("font-weight", "bold");
			}

			let perm_cell = this.add_cell(row, d, "permissions");
			let perm_container = $("<div class='row'></div>").appendTo(perm_cell);

			this.rights.forEach((r) => {
				if (!d.is_submittable && ["submit", "cancel", "amend"].includes(r)) return;
				if (d.in_create && ["create", "delete"].includes(r)) return;
				this.add_check(perm_container, d, r);
			});

			// buttons
			this.add_delete_button(row, d);
		});
	}

	add_cell(row, d, fieldname) {
		return $("<td>")
			.appendTo(row)
			.attr("data-fieldname", fieldname)
			.addClass("pt-4")
			.html(__(d[fieldname]));
	}

	add_check(cell, d, fieldname, label, description = "") {
		if (!label) label = toTitle(fieldname.replace(/_/g, " "));
		if (d.permlevel > 0 && ["read", "write"].indexOf(fieldname) == -1) {
			return;
		}

		let checkbox = $(
			`<div class='col-md-4'>
				<div class='checkbox'>
					<label><input type='checkbox'>${__(label)}</input></label>
					<p class='help-box small text-muted'>${__(description)}</p>
				</div>
			</div>`
		)
			.appendTo(cell)
			.attr("data-fieldname", fieldname);

		checkbox
			.find("input")
			.prop("checked", d[fieldname] ? true : false)
			.attr("data-ptype", fieldname)
			.attr("data-role", d.role)
			.attr("data-permlevel", d.permlevel)
			.attr("data-if_owner", d.if_owner)
			.attr("data-doctype", d.parent);

		checkbox.find("label").css("text-transform", "capitalize");

		return checkbox;
	}

	setup_if_owner(d, role_cell) {
		this.add_check(role_cell, d, "if_owner", "Only if Creator")
			.removeClass("col-md-4")
			.css({ "margin-top": "15px" });
	}

	get rights() {
		return [
			"select",
			"read",
			"write",
			"create",
			"delete",
			"submit",
			"cancel",
			"amend",
			"print",
			"email",
			"report",
			"import",
			"export",
			"set_user_permissions",
			"share",
		];
	}

	set_show_users(cell, role) {
		cell.html("<a class='grey' href='#'>" + __(role) + "</a>")
			.find("a")
			.attr("data-role", role)
			.click(function () {
				let role = $(this).attr("data-role");
				frappe.call({
					module: "frappe.core",
					page: "permission_manager",
					method: "get_users_with_role",
					args: {
						role: role,
					},
					callback: function (r) {
						r.message = $.map(r.message, function (p) {
							return $.format('<a href="/app/user/{0}">{1}</a>', [p, p]);
						});
						frappe.msgprint(
							__("Users with role {0}:", [__(role)]) +
								"<br>" +
								r.message.join("<br>")
						);
					},
				});
				return false;
			});
	}

	add_delete_button(row, d) {
		$(
			`<button class='btn btn-danger btn-remove-perm btn-xs'>${frappe.utils.icon(
				"delete"
			)}</button>`
		)
			.appendTo($(`<td class="pt-4">`).appendTo(row))
			.attr("data-doctype", d.parent)
			.attr("data-role", d.role)
			.attr("data-permlevel", d.permlevel)
			.on("click", () => {
				return frappe.call({
					module: "frappe.core",
					page: "permission_manager",
					method: "remove",
					args: {
						doctype: d.parent,
						role: d.role,
						permlevel: d.permlevel,
						if_owner: d.if_owner,
					},
					callback: (r) => {
						if (r.exc) {
							frappe.msgprint(__("Did not remove"));
						} else {
							this.refresh();
						}
					},
				});
			});
	}

	add_check_events() {
		let me = this;
		this.body.on("click", ".show-user-permissions", () => {
			frappe.route_options = { allow: this.get_doctype() || "" };
			frappe.set_route("List", "User Permission");
		});

		this.body.on("click", "input[type='checkbox']", function () {
			frappe.dom.freeze();
			let chk = $(this);
			let args = {
				role: chk.attr("data-role"),
				permlevel: chk.attr("data-permlevel"),
				doctype: chk.attr("data-doctype"),
				ptype: chk.attr("data-ptype"),
				value: chk.prop("checked") ? 1 : 0,
				if_owner: chk.attr("data-if_owner"),
			};
			return frappe.call({
				module: "frappe.core",
				page: "permission_manager",
				method: "update",
				args: args,
				callback: (r) => {
					frappe.dom.unfreeze();
					if (r.exc) {
						// exception: reverse
						chk.prop("checked", !chk.prop("checked"));
					} else {
						me.get_perm(args.role)[args.ptype] = args.value;
					}
				},
			});
		});
	}

	show_add_rule() {
		this.page.set_primary_action(
			__("Add A New Rule"),
			() => {
				let d = new frappe.ui.Dialog({
					title: __("Add New Permission Rule"),
					fields: [
						{
							fieldtype: "Select",
							label: __("Document Type"),
							options: this.options.doctypes,
							reqd: 1,
							fieldname: "parent",
						},
						{
							fieldtype: "Select",
							label: __("Role"),
							options: this.options.roles,
							reqd: 1,
							fieldname: "role",
						},
						{
							fieldtype: "Select",
							label: __("Permission Level"),
							options: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
							reqd: 1,
							fieldname: "permlevel",
							description: __(
								"Level 0 is for document level permissions, higher levels for field level permissions."
							),
						},
					],
				});
				if (this.get_doctype()) {
					d.set_value("parent", this.get_doctype());
					d.get_input("parent").prop("disabled", true);
				}
				if (this.get_role()) {
					d.set_value("role", this.get_role());
					d.get_input("role").prop("disabled", true);
				}
				d.set_value("permlevel", "0");
				d.set_primary_action(__("Add"), () => {
					let args = d.get_values();
					if (!args) {
						return;
					}
					frappe.call({
						module: "frappe.core",
						page: "permission_manager",
						method: "add",
						args: args,
						callback: (r) => {
							if (r.exc) {
								frappe.msgprint(__("Did not add"));
							} else {
								this.refresh();
							}
						},
					});
					d.hide();
				});
				d.show();
			},
			"small-add"
		);
	}

	make_reset_button() {
		this.page.set_secondary_action(__("Restore Original Permissions"), () => {
			this.get_standard_permissions((data) => {
				this.reset_std_permissions(data);
			});
		});
	}

	get_perm(role) {
		return $.map(this.perm_list, function (d) {
			if (d.role == role) return d;
		})[0];
	}

	get_link_fields(doctype) {
		return frappe.get_children("DocType", doctype, "fields", {
			fieldtype: "Link",
			options: ["not in", ["User", "[Select]"]],
		});
	}
};
