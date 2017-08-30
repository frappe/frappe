frappe.pages['permission-manager'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Role Permissions Manager'),
		icon: "fa fa-lock",
		single_column: true
	});

	frappe.breadcrumbs.add("Setup");

	$("<div class='perm-engine' style='min-height: 200px; padding: 15px;'></div>").appendTo(page.main);
	$(frappe.render_template("permission_manager_help", {})).appendTo(page.main);
	wrapper.permission_engine = new frappe.PermissionEngine(wrapper);

}

frappe.pages['permission-manager'].refresh = function(wrapper) {
	wrapper.permission_engine.set_from_route();
}

frappe.PermissionEngine = Class.extend({
	init: function(wrapper) {
		this.wrapper = wrapper;
		this.page = wrapper.page;
		this.body = $(this.wrapper).find(".perm-engine");
		this.make();
		this.refresh();
		this.add_check_events();
	},
	make: function() {
		var me = this;

		me.make_reset_button();
		return frappe.call({
			module:"frappe.core",
			page:"permission_manager",
			method: "get_roles_and_doctypes",
			callback: function(r) {
				me.options = r.message;
				me.setup_page();
			}
		});

	},
	setup_page: function() {
		var me = this;
		this.doctype_select
			= this.wrapper.page.add_select(__("Document Types"),
				[{value: "", label: __("Select Document Type")+"..."}].concat(this.options.doctypes))
				.change(function() {
					frappe.set_route("permission-manager", $(this).val());
				});
		this.role_select
			= this.wrapper.page.add_select(__("Roles"),
				[__("Select Role")+"..."].concat(this.options.roles))
				.change(function() {
					me.refresh();
				});

		this.page.add_inner_button(__('Set User Permissions'), () => {
			return frappe.set_route('List', 'User Permission');
		});
		this.set_from_route();
	},
	set_from_route: function() {
		var me = this;
		if(!this.doctype_select) {
			// selects not yet loaded, call again after a bit
			setTimeout(function() { me.set_from_route(); }, 500);
			return;
		}
		if(frappe.get_route()[1]) {
			this.doctype_select.val(frappe.get_route()[1]);
		} else if(frappe.route_options) {
			if(frappe.route_options.doctype) {
				this.doctype_select.val(frappe.route_options.doctype);
			}
			if(frappe.route_options.role) {
				this.role_select.val(frappe.route_options.role);
			}
			frappe.route_options = null;
		}
		this.refresh();
	},
	get_standard_permissions: function(callback) {
		var doctype = this.get_doctype();
		if(doctype) {
			return frappe.call({
				module:"frappe.core",
				page:"permission_manager",
				method: "get_standard_permissions",
				args: {doctype: doctype},
				callback: callback
			});
		}
		return false;
	},
	reset_std_permissions: function(data) {
		var me = this;
		var d = frappe.confirm(__("Reset Permissions for {0}?", [me.get_doctype()]), function() {
			return frappe.call({
				module:"frappe.core",
				page:"permission_manager",
				method:"reset",
				args: {
					doctype: me.get_doctype(),
				},
				callback: function() { me.refresh(); }
			});
		});

		// show standard permissions
		var $d = $(d.wrapper).find(".frappe-confirm-message").append("<hr><h4>Standard Permissions:</h4><br>");
		var $wrapper = $("<p></p>").appendTo($d);
		$.each(data.message, function(i, d) {
			d.rights = [];
			$.each(me.rights, function(i, r) {
				if(d[r]===1) {
					d.rights.push(__(toTitle(r.replace("_", " "))));
				}
			});
			d.rights = d.rights.join(", ");
			$wrapper.append(repl('<div class="row">\
				<div class="col-xs-5"><b>%(role)s</b>, Level %(permlevel)s</div>\
				<div class="col-xs-7">%(rights)s</div>\
			</div><br>', d));
		});

	},
	get_doctype: function() {
		var doctype = this.doctype_select.val();
		return this.doctype_select.get(0).selectedIndex==0 ? null : doctype;
	},
	get_role: function() {
		var role = this.role_select.val();
		return this.role_select.get(0).selectedIndex==0 ? null : role;
	},
	refresh: function() {
		var me = this;
		if(!me.doctype_select) {
			this.body.html("<p class='text-muted'>" + __("Loading") + "...</p>");
			return;
		}
		if(!me.get_doctype() && !me.get_role()) {
			this.body.html("<p class='text-muted'>"+__("Select Document Type or Role to start.")+"</p>");
			return;
		}
		// get permissions
		frappe.call({
			module: "frappe.core",
			page: "permission_manager",
			method: "get_permissions",
			args: {
				doctype: me.get_doctype(),
				role: me.get_role()
			},
			callback: function(r) {
				me.render(r.message);
			}
		});
	},
	render: function(perm_list) {
		this.body.empty();
		this.perm_list = perm_list || [];
		if(!this.perm_list.length) {
			this.body.html("<p class='text-muted'>"
				+__("No Permissions set for this criteria.")+"</p>");
		} else {
			this.show_permission_table(this.perm_list);
		}
		this.show_add_rule();
		this.make_reset_button();
	},
	show_permission_table: function(perm_list) {

		var me = this;
		this.table = $("<div class='table-responsive'>\
			<table class='table table-bordered'>\
				<thead><tr></tr></thead>\
				<tbody></tbody>\
			</table>\
		</div>").appendTo(this.body);

		$.each([[__("Document Type"), 150], [__("Role"), 170], [__("Level"), 40],
			[__("Permissions"), 350], ["", 40]], function(i, col) {
			$("<th>").html(col[0]).css("width", col[1]+"px")
				.appendTo(me.table.find("thead tr"));
		});

		$.each(perm_list, function(i, d) {
			if(d.parent==="DocType") { return; }
			if(!d.permlevel) d.permlevel = 0;
			var row = $("<tr>").appendTo(me.table.find("tbody"));
			me.add_cell(row, d, "parent");
			var role_cell = me.add_cell(row, d, "role");
			me.set_show_users(role_cell, d.role);

			if (d.permlevel===0) {
				me.setup_user_permissions(d, role_cell);
				me.setup_if_owner(d, role_cell);
			}

			var cell = me.add_cell(row, d, "permlevel");
			if(d.permlevel==0) {
				cell.css("font-weight", "bold");
				row.addClass("warning");
			}

			var perm_cell = me.add_cell(row, d, "permissions").css("padding-top", 0);
			var perm_container = $("<div class='row'></div>").appendTo(perm_cell);

			$.each(me.rights, function(i, r) {
				me.add_check(perm_container, d, r);
			});

			// buttons
			me.add_delete_button(row, d);
		});
	},

	add_cell: function(row, d, fieldname) {
		return $("<td>").appendTo(row)
			.attr("data-fieldname", fieldname)
			.html(__(d[fieldname]));
	},

	add_check: function(cell, d, fieldname, label) {
		var me = this;

		if(!label) label = toTitle(fieldname.replace(/_/g, " "));
		if(d.permlevel > 0 && ["read", "write"].indexOf(fieldname)==-1) {
			return;
		}

		var checkbox = $("<div class='col-md-4'><div class='checkbox'>\
				<label><input type='checkbox'>"+__(label)+"</input></label>"
				+ (d.help || "") + "</div></div>").appendTo(cell)
			.attr("data-fieldname", fieldname);

		checkbox.find("input")
			.prop("checked", d[fieldname] ? true: false)
			.attr("data-ptype", fieldname)
			.attr("data-role", d.role)
			.attr("data-permlevel", d.permlevel)
			.attr("data-doctype", d.parent)

		checkbox.find("label")
			.css("text-transform", "capitalize");

		return checkbox;
	},

	setup_user_permissions: function(d, role_cell) {
		var me = this;
		d.help = `<ul class="user-permission-help small hidden"
				style="margin-left: -10px;">
				<li style="margin-top: 7px;"><a class="show-user-permission-doctypes">
					${__("Select Document Types")}</a></li>
				<li style="margin-top: 3px;"><a class="show-user-permissions">
					${__("Show User Permissions")}</a></li>
			</ul>`;

		var checkbox = this.add_check(role_cell, d, "apply_user_permissions")
			.removeClass("col-md-4")
			.css({"margin-top": "15px"});

		checkbox.find(".show-user-permission-doctypes").on("click", function() {
			me.show_user_permission_doctypes(d);
		});

		var toggle_user_permissions = function() {
			checkbox.find(".user-permission-help").toggleClass("hidden", !checkbox.find("input").prop("checked"));
		};

		toggle_user_permissions();
		checkbox.find("input").on('click', function() {
			toggle_user_permissions();
		});

		d.help = "";
	},

	setup_if_owner: function(d, role_cell) {
		var checkbox = this.add_check(role_cell, d, "if_owner")
			.removeClass("col-md-4")
			.css({"margin-top": "15px"});
	},

	rights: ["read", "write", "create", "delete", "submit", "cancel", "amend",
		"print", "email", "report", "import", "export", "set_user_permissions", "share"],

	set_show_users: function(cell, role) {
		cell.html("<a class='grey' href='#'>"+__(role)+"</a>")
			.find("a")
			.attr("data-role", role)
			.click(function() {
				var role = $(this).attr("data-role");
				frappe.call({
					module: "frappe.core",
					page: "permission_manager",
					method: "get_users_with_role",
					args: {
						role: role
					},
					callback: function(r) {
						r.message = $.map(r.message, function(p) {
							return $.format('<a href="#Form/User/{0}">{1}</a>', [p, p]);
						})
						frappe.msgprint(__("Users with role {0}:", [__(role)])
							+ "<br>" + r.message.join("<br>"));
					}
				})
				return false;
			})
	},
	add_delete_button: function(row, d) {
		var me = this;
		$("<button class='btn btn-default btn-sm'><i class='fa fa-remove'></i></button>")
			.appendTo($("<td>").appendTo(row))
			.attr("data-doctype", d.parent)
			.attr("data-role", d.role)
			.attr("data-permlevel", d.permlevel)
			.click(function() {
				return frappe.call({
					module: "frappe.core",
					page: "permission_manager",
					method: "remove",
					args: {
						doctype: $(this).attr("data-doctype"),
						role: $(this).attr("data-role"),
						permlevel: $(this).attr("data-permlevel")
					},
					callback: function(r) {
						if(r.exc) {
							frappe.msgprint(__("Did not remove"));
						} else {
							me.refresh();
						}
					}
				})
			});
	},
	add_check_events: function() {
		var me = this;

		this.body.on("click", ".show-user-permissions", function() {
			frappe.route_options = { allow: me.get_doctype() || "" };
			frappe.set_route('List', 'User Permission');
		});

		this.body.on("click", "input[type='checkbox']", function() {
			var chk = $(this);
			var args = {
				role: chk.attr("data-role"),
				permlevel: chk.attr("data-permlevel"),
				doctype: chk.attr("data-doctype"),
				ptype: chk.attr("data-ptype"),
				value: chk.prop("checked") ? 1 : 0
			}
			return frappe.call({
				module: "frappe.core",
				page: "permission_manager",
				method: "update",
				args: args,
				callback: function(r) {
					if(r.exc) {
						// exception: reverse
						chk.prop("checked", !chk.prop("checked"));
					} else {
						me.get_perm(args.role)[args.ptype]=args.value;
					}
				}
			})
		})
	},
	show_add_rule: function() {
		var me = this;
		$("<button class='btn btn-default btn-primary btn-sm'><i class='fa fa-plus'></i> "
			+__("Add A New Rule")+"</button>")
			.appendTo($("<p class='permission-toolbar'>").appendTo(this.body))
			.click(function() {
				var d = new frappe.ui.Dialog({
					title: __("Add New Permission Rule"),
					fields: [
						{fieldtype:"Select", label:__("Document Type"),
							options:me.options.doctypes, reqd:1, fieldname:"parent"},
						{fieldtype:"Select", label:__("Role"),
							options:me.options.roles, reqd:1,fieldname:"role"},
						{fieldtype:"Select", label:__("Permission Level"),
							options:[0,1,2,3,4,5,6,7,8,9], reqd:1, fieldname: "permlevel",
							description: __("Level 0 is for document level permissions, \
								higher levels for field level permissions.")}
					]
				});
				if(me.get_doctype()) {
					d.set_value("parent", me.get_doctype());
					d.get_input("parent").prop("disabled", true);
				}
				if(me.get_role()) {
					d.set_value("role", me.get_role());
					d.get_input("role").prop("disabled", true);
				}
				d.set_value("permlevel", "0");
				d.set_primary_action(__('Add'), function() {
					var args = d.get_values();
					if(!args) {
						return;
					}
					frappe.call({
						module: "frappe.core",
						page: "permission_manager",
						method: "add",
						args: args,
						callback: function(r) {
							if(r.exc) {
								frappe.msgprint(__("Did not add"));
							} else {
								me.refresh();
							}
						}
					})
					d.hide();
				});
				d.show();
			});
	},

	show_user_permission_doctypes: function(d) {
		var me = this;
		if (!d.dialog) {
			var fields = [];
			for (var i=0, l=d.linked_doctypes.length; i<l; i++) {
				fields.push({
					fieldtype: "Check",
					label: __("If {0} is permitted", ["<b>" + __(d.linked_doctypes[i]) + "</b>"]),
					fieldname: d.linked_doctypes[i]
				});
			}

			fields.push({
				fieldtype: "Button",
				label: __("Set"),
				fieldname: "set_user_permission_doctypes"
			})

			var dialog = new frappe.ui.Dialog({
				title: __('Apply Rule'),
				fields: fields
			});

			var fields_to_check = d.user_permission_doctypes
				? JSON.parse(d.user_permission_doctypes) : [];

			for (var i=0, l=fields_to_check.length; i<l; i++) {
				dialog.set_value(fields_to_check[i], 1);
			}

			var btn = dialog.get_input("set_user_permission_doctypes");
			btn.on("click", function() {
				var values = dialog.get_values();
				var user_permission_doctypes = [];
				$.each(values, function(key, val) {
					if (val) {
						user_permission_doctypes.push(key);
					}
				});
				if (!user_permission_doctypes || !user_permission_doctypes.length ||
					user_permission_doctypes.length === d.linked_doctypes.length) {
					// if all checked
					user_permission_doctypes = undefined;
				} else {
					user_permission_doctypes.sort();
					user_permission_doctypes = JSON.stringify(user_permission_doctypes);
				}

				frappe.call({
					module: "frappe.core",
					page: "permission_manager",
					method: "update",
					args: {
						doctype: d.parent,
						role: d.role,
						permlevel: d.permlevel,
						ptype: "user_permission_doctypes",
						value: user_permission_doctypes
					},
					callback: function(r) {
						if(r.exc) {
							frappe.msgprint(__("Did not set"));
						} else {
							var msg = frappe.msgprint(__("Saved!"));
							setTimeout(function() { msg.hide(); }, 3000);
							d.user_permission_doctypes = user_permission_doctypes;
							dialog.hide();
							if(r.message==='refresh') {
								me.refresh();
							}
						}
					}
				});
			});

			d.dialog = dialog;
		}

		d.dialog.show();
	},

	make_reset_button: function() {
		var me = this;
		$('<button class="btn btn-default btn-sm" style="margin-left: 10px;">\
			<i class="fa fa-refresh"></i> ' + __("Restore Original Permissions") + '</button>')
			.appendTo(this.body.find(".permission-toolbar"))
			.on("click", function() {
				me.get_standard_permissions(function(data) {
					me.reset_std_permissions(data);
				});
			})
	},

	get_perm: function(role) {
		return $.map(this.perm_list, function(d) { if(d.role==role) return d; })[0];
	},
	get_link_fields: function(doctype) {
		return frappe.get_children("DocType", doctype, "fields",
			{fieldtype:"Link", options:["not in", ["User", '[Select]']]});
	}
});
