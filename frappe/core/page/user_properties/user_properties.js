frappe.pages['user-properties'].onload = function(wrapper) { 
	frappe.ui.make_app_page({
		parent: wrapper,
		title: 'User Permission Restrictions',
		single_column: true
	});					
	$(wrapper).find(".layout-main").html("<div class='user-settings' style='min-height: 200px;'></div>\
	<table class='table table-bordered' style='background-color: #f9f9f9;'>\
	<tr><td>\
	<h4><i class='icon-question-sign'></i> "+__("Quick Help for Permission Restrictions")+":</h4>\
	<ol>\
	<li>"+__("Apart from the existing Permission Rules, you can apply addition restriction based on Type.")+"</li>\
	<li>"+__("These restrictions will apply for all transactions linked to the restricted record.")
		 +__("For example, if user X is restricted to company C, user X will not be able to see any transaction that has company C as a linked value.")+"</li>\
	<li>"+__("These will also be set as default values for those links.")+"</li>\
	<li>"+__("A user can be restricted to multiple records of the same type.")+"</li>\
	</ol>\
	</tr></td>\
	</table>");
	wrapper.user_properties = new frappe.UserProperties(wrapper);
}

frappe.pages['user-properties'].refresh = function(wrapper) {
	wrapper.user_properties.set_from_route();
}

frappe.UserProperties = Class.extend({
	init: function(wrapper) {
		this.wrapper = wrapper;
		this.body = $(this.wrapper).find(".user-settings");
		this.filters = {};
		this.make();
		this.refresh();
	},
	make: function() {
		var me = this;
		return frappe.call({
			module:"frappe.core",
			page:"user_properties",
			method: "get_users_and_links",
			callback: function(r) {
				me.options = r.message;
				
				me.filters.user = me.wrapper.appframe.add_field({
					fieldname: "user",
					label: __("User"),
					fieldtype: "Select",
					options: (["Select User..."].concat(r.message.users)).join("\n")
				});
				
				me.filters.property = me.wrapper.appframe.add_field({
					fieldname: "property",
					label: __("Property"),
					fieldtype: "Select",
					options: (["Select Property..."].concat(me.get_link_names())).join("\n")
				});
				
				me.filters.restriction = me.wrapper.appframe.add_field({
					fieldname: "restriction",
					label: __("Restriction"),
					fieldtype: "Link",
					options: "[Select]"
				});
				
				// bind change event
				$.each(me.filters, function(k, f) {
					f.$input.on("change", function() {
						me.refresh();
					});
				});
				
				// change options in restriction link
				me.filters.property.$input.on("change", function() {
					me.filters.restriction.df.options = $(this).val();
				});
				
				me.set_from_route();
			}
		});
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
		return user=="Select User..." ? null : user;
	},
	get_property: function() {
		var property = this.filters.property.$input.val();
		return property=="Select Property..." ? null : property;
	},
	get_restriction: function() {
		// autosuggest hack!
		var restriction = this.filters.restriction.$input.val();
		return (restriction === "%") ? null : restriction;
	},
	render: function(prop_list) {
		this.body.empty();
		this.prop_list = prop_list;
		if(!prop_list || !prop_list.length) {
			this.body.html("<div class='alert alert-info'>"+__("No User Restrictions found.")+"</div>");
		} else {
			this.show_property_table();
		}
		this.show_add_property();
	},
	refresh: function() {
		var me = this;
		if(!me.filters.user) {
			this.body.html("<div class='alert alert-info'>"+__("Loading")+"...</div>");
			return;
		}
		if(!me.get_user() && !me.get_property()) {
			this.body.html("<div class='alert alert-warning'>"+__("Select User or Property to start.")+"</div>");
			return;
		}
		// get permissions
		return frappe.call({
			module: "frappe.core",
			page: "user_properties",
			method: "get_properties",
			args: {
				parent: me.get_user(),
				defkey: me.get_property(),
				defvalue: me.get_restriction()
			},
			callback: function(r) {
				me.render(r.message);
			}
		});		
	},
	show_property_table: function() {
		var me = this;
		this.table = $("<table class='table table-bordered'>\
			<thead><tr></tr></thead>\
			<tbody></tbody>\
		</table>").appendTo(this.body);
		
		$.each([[__("User"), 150], [__("Type"), 150], [__("Restricted To"),150], ["", 50]], 
			function(i, col) {
			$("<th>").html(col[0]).css("width", col[1]+"px")
				.appendTo(me.table.find("thead tr"));
		});

				
		$.each(this.prop_list, function(i, d) {
			var row = $("<tr>").appendTo(me.table.find("tbody"));
			
			$("<td>").html('<a href="#Form/User/'+encodeURIComponent(d.parent)+'">'
				+d.parent+'</a>').appendTo(row);
			$("<td>").html(d.defkey).appendTo(row);
			$("<td>").html(d.defvalue).appendTo(row);
			
			me.add_delete_button(row, d);
		});

	},
	add_delete_button: function(row, d) {
		var me = this;
		$("<button class='btn btn-small btn-default'><i class='icon-remove'></i></button>")
			.appendTo($("<td>").appendTo(row))
			.attr("data-name", d.name)
			.attr("data-user", d.parent)
			.attr("data-defkey", d.defkey)
			.attr("data-defvalue", d.defvalue)
			.click(function() {
				return frappe.call({
					module: "frappe.core",
					page: "user_properties",
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
	
	show_add_property: function() {
		var me = this;
		$("<button class='btn btn-info'>"+__("Add A Restriction")+"</button>")
			.appendTo($("<p>").appendTo(this.body))
			.click(function() {
				var d = new frappe.ui.Dialog({
					title: "Add New Property",
					fields: [
						{fieldtype:"Select", label:__("User"),
							options:me.options.users, reqd:1, fieldname:"user"},
						{fieldtype:"Select", label: __("Property"), fieldname:"defkey",
							options:me.get_link_names(), reqd:1},
						{fieldtype:"Link", label:__("Value"), fieldname:"defvalue",
							options:'[Select]', reqd:1},
						{fieldtype:"Button", label: __("Add"), fieldname:"add"},
					]
				});
				if(me.get_user()) {
					d.set_value("user", me.get_user());
					d.get_input("user").prop("disabled", true);
				}
				if(me.get_property()) {
					d.set_value("defkey", me.get_property());
					d.get_input("defkey").prop("disabled", true);
				}
				if(me.get_restriction()) {
					d.set_value("defvalue", me.get_restriction());
					d.get_input("defvalue").prop("disabled", true);
				}
				
				d.fields_dict["defvalue"].get_query = function(txt) {
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
						page: "user_properties",
						method: "add",
						args: args,
						callback: function(r) {
							if(r.exc) {
								msgprint("Did not add");
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
