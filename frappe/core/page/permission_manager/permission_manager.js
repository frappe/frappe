frappe.pages['permission-manager'].onload = function(wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Role Permissions Manager'),
		icon: "icon-lock",
		single_column: true
	});
	$(wrapper).find(".layout-main").html("<div class='perm-engine' style='min-height: 200px;'></div>"
		+ permissions_help);
	wrapper.permission_engine = new frappe.PermissionEngine(wrapper);

}

frappe.pages['permission-manager'].refresh = function(wrapper) {
	wrapper.permission_engine.set_from_route();
}

frappe.PermissionEngine = Class.extend({
	init: function(wrapper) {
		this.wrapper = wrapper;
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
				me.setup_appframe();
			}
		});

	},
	setup_appframe: function() {
		var me = this;
		this.doctype_select
			= this.wrapper.appframe.add_select("doctypes",
				[{value: "", label: __("Select Document Type")+"..."}].concat(this.options.doctypes))
				.change(function() {
					frappe.set_route("permission-manager", $(this).val());
				});
		this.role_select
			= this.wrapper.appframe.add_select("roles",
				[__("Select Role")+"..."].concat(this.options.roles))
				.change(function() {
					me.refresh();
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
					doctype:me.get_doctype(),
				},
				callback: function() { me.refresh(); }
			});
		});

		// show standard permissions
		var $d = $(d.wrapper).find(".frappe-confirm-message").append("<hr><h4>Standard Permissions</h4>");
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
			this.body.html("<div class='alert alert-info'>Loading...</div>");
			return;
		}
		if(!me.get_doctype() && !me.get_role()) {
			this.body.html("<div class='alert alert-info'>"+__("Select Document Type or Role to start.")+"</div>");
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
			this.body.html("<div class='alert alert-warning'>"
				+__("No Permissions set for this criteria.")+"</div>");
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

		$.each([["Document Type", 150], ["Role", 170], ["Level", 40],
			["Permissions", 350], ["", 40]], function(i, col) {
			$("<th>").html(col[0]).css("width", col[1]+"px")
				.appendTo(me.table.find("thead tr"));
		});

		var add_cell = function(row, d, fieldname) {
			return $("<td>").appendTo(row)
				.attr("data-fieldname", fieldname)
				.html(d[fieldname]);
		};

		var add_check = function(cell, d, fieldname, label, without_grid) {
			if(!label) label = fieldname.replace(/_/g, " ");
			if(d.permlevel > 0 && ["read", "write"].indexOf(fieldname)==-1) {
				return;
			}

			var checkbox = $("<div class='col-md-4'><div class='checkbox'>\
					<label><input type='checkbox'>"+__(label)+"</input></label>"
					+ (d.help || "") + "</div></div>").appendTo(cell)
				.attr("data-fieldname", fieldname)
				.css("text-transform", "capitalize");

			checkbox.find("input")
				.prop("checked", d[fieldname] ? true: false)
				.attr("data-ptype", fieldname)
				.attr("data-name", d.name)
				.attr("data-doctype", d.parent)

			return checkbox;
		};

		$.each(perm_list, function(i, d) {
			if(!d.permlevel) d.permlevel = 0;
			var row = $("<tr>").appendTo(me.table.find("tbody"));
			add_cell(row, d, "parent");
			var role_cell = add_cell(row, d, "role");
			me.set_show_users(role_cell, d.role);

			if (d.permlevel===0) {
				d.help = '<div style="margin-left: 20px;">\
					<a class="show-user-permissions small">Show User Pemissions</a></div>';
				add_check(role_cell, d, "apply_user_permissions")
					.removeClass("col-md-4")
					.css({"margin-top": "15px"});
				d.help = "";
			}

			var cell = add_cell(row, d, "permlevel");
			if(d.permlevel==0) {
				cell.css("font-weight", "bold");
				row.addClass("warning");
			}

			var perm_cell = add_cell(row, d, "permissions").css("padding-top", 0);
			var perm_container = $("<div class='row'></div>").appendTo(perm_cell);

			$.each(me.rights, function(i, r) {
				add_check(perm_container, d, r);
			});

			// buttons
			me.add_delete_button(row, d);
		});
	},
	rights: ["read", "write", "create", "delete", "submit", "cancel", "amend",
		"print", "email", "report", "import", "export", "set_user_permissions"],

	set_show_users: function(cell, role) {
		cell.html("<a href='#'>"+role+"</a>")
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
						msgprint(__("Users with role {0}:", [role])
							+ "<br>" + r.message.join("<br>"));
					}
				})
				return false;
			})
	},
	add_delete_button: function(row, d) {
		var me = this;
		$("<button class='btn btn-default btn-small'><i class='icon-remove'></i></button>")
			.appendTo($("<td>").appendTo(row))
			.attr("data-name", d.name)
			.attr("data-doctype", d.parent)
			.click(function() {
				return frappe.call({
					module: "frappe.core",
					page: "permission_manager",
					method: "remove",
					args: {
						name: $(this).attr("data-name"),
						doctype: $(this).attr("data-doctype")
					},
					callback: function(r) {
						if(r.exc) {
							msgprint(__("Did not remove"));
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
			frappe.route_options = { doctype: me.get_doctype() || "" };
			frappe.set_route("user-permissions");
		});

		this.body.on("click", "input[type='checkbox']", function() {
			var chk = $(this);
			var args = {
				name: chk.attr("data-name"),
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
						me.get_perm(args.name)[args.ptype]=args.value;
					}
				}
			})
		})
	},
	show_add_rule: function() {
		var me = this;
		$("<button class='btn btn-default btn-primary'><i class='icon-plus'></i> "
			+__("Add A New Rule")+"</button>")
			.appendTo($("<p class='permission-toolbar'>").appendTo(this.body))
			.click(function() {
				var d = new frappe.ui.Dialog({
					title: __("Add New Permission Rule"),
					fields: [
						{fieldtype:"Select", label:"Document Type",
							options:me.options.doctypes, reqd:1, fieldname:"parent"},
						{fieldtype:"Select", label:"Role",
							options:me.options.roles, reqd:1},
						{fieldtype:"Select", label:"Permission Level",
							options:[0,1,2,3,4,5,6,7,8,9], reqd:1, fieldname: "permlevel",
							description: __("Level 0 is for document level permissions, higher levels for field level permissions.")},
						{fieldtype:"Button", label:"Add"},
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
				d.get_input("add").click(function() {
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
								msgprint(__("Did not add"));
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

	make_reset_button: function() {
		var me = this;
		$('<button class="btn btn-default" style="margin-left: 10px;">\
			<i class="icon-refresh"></i> Restore Original Permissions</button>')
			.appendTo(this.body.find(".permission-toolbar"))
			.on("click", function() {
				me.get_standard_permissions(function(data) {
					me.reset_std_permissions(data);
				});
			})
	},

	get_perm: function(name) {
		return $.map(this.perm_list, function(d) { if(d.name==name) return d; })[0];
	},
	get_user_fields: function(doctype) {
		var user_fields = frappe.get_children("DocType", doctype, "fields", {fieldtype:"Link", options:"User"})
		user_fields = user_fields.concat(frappe.get_children("DocType", doctype, "fields",
			{fieldtype:"Select", link_doctype:"User"}))

		return 	user_fields
	},
	get_link_fields: function(doctype) {
		return frappe.get_children("DocType", doctype, "fields",
			{fieldtype:"Link", options:["not in", ["User", '[Select]']]});
	}
})

var permissions_help = ['<table class="table table-bordered" style="background-color: #f9f9f9; margin-top: 30px;">',
	'<tr><td>',
		'<h4><i class="icon-question-sign"></i> ',
			__('Quick Help for Setting Permissions'),
		':</h4>',
		'<ol>',
			'<li>',
				__('Permissions are set on Roles and Document Types (called DocTypes) by setting rights like Read, Write, Create, Delete, Submit, Cancel, Amend, Report, Import, Export, Print, Email and Set User Permissions.'),
			'</li>',
			'<li>',
				__('Permissions get applied on Users based on what Roles they are assigned.'),
			'</li>',
			'<li>',
				__('Roles can be set for users from their User page.')
				+ ' (<a href="#List/User">' + __("Setup > User") + '</a>)',
			'</li>',
			'<li>',
				__('The system provides many pre-defined roles. You can add new roles to set finer permissions.')
				+ ' (<a href="#List/Role">' + __("Add a New Role") + '</a>)',
			'</li>',
			'<li>',
				__('Permissions are automatically translated to Standard Reports and Searches.'),
			'</li>',
			'<li>',
				__('As a best practice, do not assign the same set of permission rule to different Roles. Instead, set multiple Roles to the same User.'),
			'</li>',
		'</ol>',
	'</td></tr>',
	'<tr><td>',
		'<h4><i class="icon-hand-right"></i> ',
			__('Meaning of Submit, Cancel, Amend'),
		':</h4>',
		'<ol>',
			'<li>',
				__('Certain documents, like an Invoice, should not be changed once final. The final state for such documents is called Submitted. You can restrict which roles can Submit.'),
			'</li>',
			'<li>',
				__('You can change Submitted documents by cancelling them and then, amending them.'),
			'</li>',
			'<li>',
				__('When you Amend a document after Cancel and save it, it will get a new number that is a version of the old number.'),
			'</li>',
			'<li>',
				__("For example if you cancel and amend 'INV004' it will become a new document 'INV004-1'. This helps you to keep track of each amendment."),
			'</li>',
		'</ol>',
	'</td></tr>',
	'<tr><td>',
		'<h4><i class="icon-signal"></i> ',
			__('Permission Levels'),
		':</h4>',
		'<ol>',
			'<li>',
				__("Permissions at level 0 are 'Document Level' permissions, i.e. they are primary for access to the document."),
			'</li>',
			'<li>',
				__('If a Role does not have access at Level 0, then higher levels are meaningless.'),
			'</li>',
			'<li>',
				__("Permissions at higher levels are 'Field Level' permissions. All Fields have a 'Permission Level' set against them and the rules defined at that permissions apply to the field. This is useful in case you want to hide or make certain field read-only for certain Roles."),
			'</li>',
			'<li>',
				__('You can use Customize Form to set levels on fields.')
				+ ' (<a href="#Form/Customize Form">Setup > Customize Form</a>)',
			'</li>',
		'</ol>',
	'</td></tr>',
	'<tr><td>',
		'<h4><i class="icon-shield"></i> ',
			__('User Permissions'),
		':</h4>',
		'<ol>',
			'<li>',
				__("To give acess to a role for only specific records, check the 'Apply User Permissions'. User Permissions are used to limit users with such role to specific records.")
				+ ' (<a href="#user-permissions">' + __('Setup > User Permissions Manager') + '</a>)',
			'</li>',
			'<li>',
				__("Once you have set this, the users will only be able access documents (eg. Blog Post) where the link exists (eg. Blogger)."),
			'</li>',
			'<li>',
				__("Apart from System Manager, roles with 'Set User Permissions' right can set permissions for other users for that Document Type."),
			'</li>',
		'</ol>',
	'</td></tr>',
'</table>',
'<p>',
	__("If these instructions where not helpful, please add in your suggestions on GitHub Issues.")
	+ ' (<a href="https://github.com/frappe/frappe/issues" target="_blank">' + __("Submit an Issue") + '</a>)',
'</p>'].join("\n");
