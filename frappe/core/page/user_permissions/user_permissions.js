frappe.pages['user-permissions'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("User Permissions Manager"),
		icon: "fa fa-shield",
		single_column: true
	});

	frappe.breadcrumbs.add("Setup");

	$("<div class='user-settings' \
		style='min-height: 200px; padding: 15px;'></div>\
	<p style='padding: 15px; padding-bottom: 0px;'>\
		<a class='view-role-permissions grey'>" + __("Edit Role Permissions") + "</a>\
	</p><hr><div style='padding: 0px 15px;'>\
		<h4>"+__("Help for User Permissions")+":</h4>\
		<ol>\
			<li>"
			+ __("Apart from Role based Permission Rules, you can apply User Permissions based on DocTypes.")
			+ "</li>"

			+ "<li>"
			+ __("These permissions will apply for all transactions where the permitted record is linked. For example, if Company C is added to User Permissions of user X, user X will only be able to see transactions that has company C as a linked value.")
			+ "</li>"

			+ "<li>"
			+ __("These will also be set as default values for those links, if only one such permission record is defined.")
			+ "</li>"

			+ "<li>"
			+ __("A user can be permitted to multiple records of the same DocType.")
			+ "</li>\
		</ol></div>").appendTo(page.main);
	wrapper.user_permissions = new frappe.UserPermissions(wrapper);
}

frappe.pages['user-permissions'].refresh = function(wrapper) {
	wrapper.user_permissions.set_from_route();
}

frappe.UserPermissions = Class.extend({
	init: function(wrapper) {
		this.wrapper = wrapper;
		this.body = $(this.wrapper).find(".user-settings");
		this.filters = {};
		this.make();
		this.refresh();
	},
	make: function() {
		var me = this;

		$(this.wrapper).find(".view-role-permissions").on("click", function() {
				frappe.route_options = { doctype: me.get_doctype() || "" };
				frappe.set_route("permission-manager");
			})

		return frappe.call({
			module:"frappe.core",
			page:"user_permissions",
			method: "get_users_and_links",
			callback: function(r) {
				me.options = r.message;

				me.filters.user = me.wrapper.page.add_field({
					fieldname: "user",
					label: __("User"),
					fieldtype: "Select",
					options: ([__("Select User") + "..."].concat(r.message.users)).join("\n")
				});

				me.filters.doctype = me.wrapper.page.add_field({
					fieldname: "doctype",
					label: __("DocType"),
					fieldtype: "Select",
					options: ([__("Select DocType") + "..."].concat(me.get_link_names())).join("\n")
				});

				me.filters.user_permission = me.wrapper.page.add_field({
					fieldname: "user_permission",
					label: __("Name"),
					fieldtype: "Link",
					options: "[Select]"
				});

				if(roles.indexOf("System Manager")!==-1) {
					me.download = me.wrapper.page.add_field({
						fieldname: "download",
						label: __("Download"),
						fieldtype: "Button",
						icon: "fa fa-download"
					});

					me.upload = me.wrapper.page.add_field({
						fieldname: "upload",
						label: __("Upload"),
						fieldtype: "Button",
						icon: "fa fa-upload"
					});
				}

				// bind change event
				$.each(me.filters, function(k, f) {
					f.$input.on("change", function() {
						me.refresh();
					});
				});

				// change options in user_permission link
				me.filters.doctype.$input.on("change", function() {
					me.filters.user_permission.df.options = me.get_doctype();
				});

				me.set_from_route();
				me.setup_download_upload();
			}
		});
	},
	setup_download_upload: function() {
		var me = this;
		me.download.$input.on("click", function() {
			window.location.href = frappe.urllib.get_base_url()
				+ "/api/method/frappe.core.page.user_permissions.user_permissions.get_user_permissions_csv";
		});

		me.upload.$input.on("click", function() {
			var d = new frappe.ui.Dialog({
				title: __("Upload User Permissions"),
				fields: [
					{
						fieldtype:"HTML",
						options: '<p class="text-muted"><ol>'+
							"<li>"+__("Upload CSV file containing all user permissions in the same format as Download.")+"</li>"+
							"<li><strong>"+__("Any existing permission will be deleted / overwritten.")+"</strong></li>"+
						'</p>'
					},
					{
						fieldtype:"Attach", fieldname:"attach",
					}
				],
				primary_action_label: __("Upload and Sync"),
				primary_action: function() {
					var filedata = d.fields_dict.attach.get_value();
					if(!filedata) {
						msgprint(_("Please attach a file"));
						return;
					}
					frappe.call({
						method:"frappe.core.page.user_permissions.user_permissions.import_user_permissions",
						args: {
							filedata: filedata
						},
						callback: function(r) {
							if(!r.exc) {
								msgprint(__("Permissions Updated"));
								d.hide();
							}
						}
					});
				}
			});
			d.show();
		})
	},
	get_link_names: function() {
		return this.options.link_fields;
	},
	set_from_route: function() {
		var me = this;
		if(frappe.route_options && this.filters && !$.isEmptyObject(this.filters)) {
			$.each(frappe.route_options, function(key, value) {
				if(me.filters[key] && frappe.route_options[key]!=null)
					me.set_filter(key, value);
			});
			frappe.route_options = null;
		}
		this.refresh();
	},
	set_filter: function(key, value) {
		this.filters[key].$input.val(value);
	},
	get_user: function() {
		var user = this.filters.user.$input.val();
		return user== __("Select User") + "..." ? null : user;
	},
	get_doctype: function() {
		var doctype = this.filters.doctype.$input.val();
		return doctype== __("Select DocType") + "..." ? null : doctype;
	},
	get_user_permission: function() {
		// autosuggest hack!
		var user_permission = this.filters.user_permission.$input.val();
		return (user_permission === "%") ? null : user_permission;
	},
	render: function(prop_list) {
		var me = this;
		this.body.empty();
		this.prop_list = prop_list;
		if(!prop_list || !prop_list.length) {
			this.add_message(__("No User Restrictions found."));
		} else {
			this.show_user_permissions_table();
		}
		this.show_add_user_permission();
		if(this.get_user() && this.get_doctype()) {
			$('<button class="btn btn-default btn-sm" style="margin-left: 10px;">\
				Show Allowed Documents</button>').appendTo(this.body.find(".btn-area")).on("click", function() {
					frappe.route_options = {doctype: me.get_doctype(), user:me.get_user() };
					frappe.set_route("query-report/Permitted Documents For User");
				});
		}
	},
	add_message: function(txt) {
		$('<p class="text-muted">' + txt + '</p>').appendTo(this.body);
	},
	refresh: function() {
		var me = this;
		if(!me.filters.user) {
			this.body.html("<p class='text-muted'>"+__("Loading")+"...</p>");
			return;
		}
		if(!me.get_user() && !me.get_doctype()) {
			this.body.html("<p class='text-muted'>"+__("Select User or DocType to start.")+"</p>");
			return;
		}
		// get permissions
		return frappe.call({
			module: "frappe.core",
			page: "user_permissions",
			method: "get_permissions",
			args: {
				parent: me.get_user(),
				defkey: me.get_doctype(),
				defvalue: me.get_user_permission()
			},
			callback: function(r) {
				me.render(r.message);
			}
		});
	},
	show_user_permissions_table: function() {
		var me = this;
		this.table = $("<table class='table table-bordered'>\
			<thead><tr></tr></thead>\
			<tbody></tbody>\
		</table>").appendTo(this.body);

		$('<p class="text-muted small">'
			+__("These restrictions will apply for Document Types where 'Apply User Permissions' is checked for the permission rule and a field with this value is present.")
			+'</p>').appendTo(this.body);

		$.each([[__("Allow User"), 150], [__("If Document Type"), 150], [__("Is"),150], ["", 50]],
			function(i, col) {
			$("<th>").html(col[0]).css("width", col[1]+"px")
				.appendTo(me.table.find("thead tr"));
		});


		$.each(this.prop_list, function(i, d) {
			var row = $("<tr>").appendTo(me.table.find("tbody"));

			$("<td>").html('<a class="grey" href="#Form/User/'+encodeURIComponent(d.parent)+'">'
				+d.parent+'</a>').appendTo(row);
			$("<td>").html(d.defkey).appendTo(row);
			$("<td>").html(d.defvalue).appendTo(row);

			me.add_delete_button(row, d);
		});

	},
	add_delete_button: function(row, d) {
		var me = this;
		$("<button class='btn btn-sm btn-default'><i class='fa fa-remove'></i></button>")
			.appendTo($("<td>").appendTo(row))
			.attr("data-name", d.name)
			.attr("data-user", d.parent)
			.attr("data-defkey", d.defkey)
			.attr("data-defvalue", d.defvalue)
			.click(function() {
				return frappe.call({
					module: "frappe.core",
					page: "user_permissions",
					method: "remove",
					args: {
						name: $(this).attr("data-name"),
						user: $(this).attr("data-user"),
						defkey: $(this).attr("data-defkey"),
						defvalue: $(this).attr("data-defvalue")
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

	show_add_user_permission: function() {
		var me = this;
		$("<button class='btn btn-default btn-sm'>"+__("Add A User Restriction")+"</button>")
			.appendTo($('<p class="btn-area">').appendTo(this.body))
			.click(function() {
				var d = new frappe.ui.Dialog({
					title: __("Add A New Restriction"),
					fields: [
						{fieldtype:"Select", label:__("Allow User"),
							options:me.options.users, reqd:1, fieldname:"user"},
						{fieldtype:"Select", label: __("If Document Type"), fieldname:"defkey",
							options:me.get_link_names(), reqd:1},
						{fieldtype:"Link", label:__("Is"), fieldname:"defvalue",
							options:'[Select]', reqd:1},
						{fieldtype:"Button", label: __("Add"), fieldname:"add"},
					]
				});
				if(me.get_user()) {
					d.set_value("user", me.get_user());
					d.get_input("user").prop("disabled", true);
				}
				if(me.get_doctype()) {
					d.set_value("defkey", me.get_doctype());
					d.get_input("defkey").prop("disabled", true);
				}
				if(me.get_user_permission()) {
					d.set_value("defvalue", me.get_user_permission());
					d.get_input("defvalue").prop("disabled", true);
				}

				d.fields_dict["defvalue"].get_query = function(txt) {
					if(!d.get_value("defkey")) {
						frappe.throw(__("Please select Document Type"));
					}

					return {
						doctype: d.get_value("defkey")
					}
				};

				d.get_input("add").click(function() {
					var args = d.get_values();
					if(!args) {
						return;
					}
					frappe.call({
						module: "frappe.core",
						page: "user_permissions",
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
	}
})
