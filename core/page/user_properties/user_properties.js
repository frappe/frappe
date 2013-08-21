wn.pages['user-properties'].onload = function(wrapper) { 
	wn.ui.make_app_page({
		parent: wrapper,
		title: 'User Properties',
		single_column: true
	});					
	$(wrapper).find(".layout-main").html("<div class='user-settings'></div>\
	<table class='table table-bordered' style='background-color: #f9f9f9;'>\
	<tr><td>\
	<h4><i class='icon-question-sign'></i> "+wn._("Quick Help for User Properties")+":</h4>\
	<ol>\
	<li>"+wn._("You can set various 'properties' to Users to set default values and apply permission rules based on the value of these properties in various forms.")+"</li>\
	<li>"+wn._("These properties are Link Type fields from all Documents.")+"</li>\
	<li>"+wn._("These properties will appear as values in forms that contain them.")+"</li>\
	<li>"+wn._("These properties can also be used to 'assign' a particular document, whose property matches with the User's property to a User. These can be set using the <a href='#permission-manager'>Permission Manager</a>")+"</li>\
	<li>"+wn._("A user can have multiple values for a property.")+"</li>\
	</ol>\
	</tr></td>\
	</table>");
	wrapper.user_properties = new wn.UserProperties(wrapper);
}

wn.pages['user-properties'].refresh = function(wrapper) { 
	wrapper.user_properties.set_from_route();
}

wn.UserProperties = Class.extend({
	init: function(wrapper) {
		this.wrapper = wrapper;
		this.body = $(this.wrapper).find(".user-settings");
		this.make();
		this.refresh();
	},
	make: function() {
		var me = this;
		return wn.call({
			module:"core",
			page:"user_properties",
			method: "get_users_and_links",
			callback: function(r) {
				me.options = r.message;
				me.user_select =
					me.wrapper.appframe.add_select("users", 
						["Select User..."].concat(r.message.users))
						.css("width", "200px")
						.change(function() {
							me.set_route();
						});
				me.property_select =
					me.wrapper.appframe.add_select("links", 
						["Select Property..."].concat(me.get_link_names()))
						.css("width", "200px")
						.change(function() {
							me.set_route();
						});
				me.set_from_route();
			}
		});
	},
	get_link_names: function() {
		return $.map(this.options.link_fields, function(l) { return l[0]; });
	},
	set_route: function() {
		wn.set_route("user-properties", this.user_select.val(), 
			this.property_select.val());
	},
	set_from_route: function() {
		var route = wn.get_route();
		if((route.length > 1) && this.user_select && this.property_select) {
			this.user_select.val(route[1]);
			this.property_select.val(route[2]);
		}
		this.refresh();
	},
	get_user: function() {
		var user = this.user_select.val();
		return user=="Select User..." ? null : user;
	},
	get_property: function() {
		var property = this.property_select.val();
		return property=="Select Property..." ? null : property;
	},
	render: function(prop_list) {
		this.body.empty();
		this.prop_list = prop_list;
		if(!prop_list.length) {
			this.body.html("<div class='alert alert-info'>"+wn._("No User Properties found.")+"</div>");
		} else {
			this.show_property_table();
		}
		this.show_add_property();
	},
	refresh: function() {
		var me = this;
		if(!me.user_select) {
			this.body.html("<div class='alert alert-info'>"+wn._("Loading")+"...</div>");
			return;
		}
		if(!me.get_user() && !me.get_property()) {
			this.body.html("<div class='alert alert-warning'>"+wn._("Select User or Property to start.")+"</div>");
			return;
		}
		// get permissions
		return wn.call({
			module: "core",
			page: "user_properties",
			method: "get_properties",
			args: {
				user: me.get_user(),
				key: me.get_property()
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
		
		$.each([[wn._("User"), 150], [wn._("Property"), 150], [wn._("Value"),150], ["", 50]], 
			function(i, col) {
			$("<th>").html(col[0]).css("width", col[1]+"px")
				.appendTo(me.table.find("thead tr"));
		});

				
		$.each(this.prop_list, function(i, d) {
			var row = $("<tr>").appendTo(me.table.find("tbody"));
			
			$("<td>").html('<a href="#Form/Profile/'+d.parent+'">'
				+d.parent+'</a>').appendTo(row);
			$("<td>").html(d.defkey).appendTo(row);
			$("<td>").html(d.defvalue).appendTo(row);
			
			me.add_delete_button(row, d);
		});

	},
	add_delete_button: function(row, d) {
		var me = this;
		$("<button class='btn btn-small'><i class='icon-remove'></i></button>")
			.appendTo($("<td>").appendTo(row))
			.attr("data-name", d.name)
			.attr("data-user", d.parent)
			.click(function() {
				return wn.call({
					module: "core",
					page: "user_properties",
					method: "remove",
					args: {
						name: $(this).attr("data-name"),
						user: $(this).attr("data-user")
					},
					callback: function(r) {
						if(r.exc) {
							msgprint("Did not remove.");
						} else {
							me.refresh();
						}
					}
				})
			});
	},
	
	show_add_property: function() {
		var me = this;
		$("<button class='btn btn-info'>"+wn._("Add A Property")+"</button>")
			.appendTo($("<p>").appendTo(this.body))
			.click(function() {
				var d = new wn.ui.Dialog({
					title: "Add New Property",
					fields: [
						{fieldtype:"Select", label:wn._("User"),
							options:me.options.users, reqd:1, fieldname:"parent"},
						{fieldtype:"Select", label: wn._("Property"), fieldname:"defkey",
							options:me.get_link_names(), reqd:1},
						{fieldtype:"Link", label:wn._("Value"), fieldname:"defvalue",
							options:'[Select]', reqd:1},
						{fieldtype:"Button", label: wn._("Add"), fieldname:"add"},
					]
				});
				if(me.get_user()) {
					d.set_value("parent", me.get_user());
					d.get_input("parent").attr("disabled", true);
				}
				if(me.get_property()) {
					d.set_value("defkey", me.get_property());
					d.get_input("defkey").attr("disabled", true);
				}
				
				d.fields_dict["defvalue"].get_query = function(txt) {
					var key = d.get_value("defkey");
					var doctype = $.map(me.options.link_fields, function(l) {
						if(l[0]==key) return l[1];
					})[0];
					
					return {
						query: "core.page.user_properties.user_properties.get_defvalue",
						filters: {
							doctype: doctype
						},
						doctype: doctype,
					}
				};
				
				d.get_input("add").click(function() {
					var args = d.get_values();
					if(!args) {
						return;
					}
					wn.call({
						module: "core",
						page: "user_properties",
						method: "add",
						args: args,
						callback: function(r) {
							if(r.exc) {
								msgprint("Did not add.");
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