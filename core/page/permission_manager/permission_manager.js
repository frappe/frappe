wn.pages['permission-manager'].onload = function(wrapper) { 
	wn.ui.make_app_page({
		parent: wrapper,
		title: wn._('Permission Manager'),
		single_column: true
	});
	$(wrapper).find(".layout-main").html("<div class='perm-engine'></div>\
	<table class='table table-bordered' style='background-color: #f9f9f9;'>\
	<tr><td>\
	<h4><i class='icon-question-sign'></i> "+wn._("Quick Help for Setting Permissions")+":</h4>\
	<ol>\
	<li>"+wn._("Permissions are set on Roles and Document Types (called DocTypes) by restricting read, edit, make new, submit, cancel, amend and report rights.")+"</li>\
	<li>"+wn._("Permissions translate to Users based on what Role they are assigned")+".</li>\
	<li>"+wn._("To set user roles, just go to <a href='#List/Profile'>Setup > Users</a> and click on the user to assign roles.")+"</li>\
	<li>"+wn._("The system provides pre-defined roles, but you can <a href='#List/Role'>add new roles</a> to set finer permissions")+".</li>\
	<li>"+wn._("Permissions are automatically translated to Standard Reports and Searches")+".</li>\
	<li>"+wn._("As a best practice, do not assign the same set of permission rule to different Roles instead set multiple Roles to the User")+".</li>\
	</ol>\
	</tr></td>\
	<tr><td>\
	<h4><i class='icon-hand-right'></i> "+wn._("Meaning of Submit, Cancel, Amend")+":</h4>\
	<ol>\
	<li>"+wn._("Certain documents should not be changed once final, like an Invoice for example. The final state for such documents is called <b>Submitted</b>. You can restrict which roles can Submit.")+"</li>\
	<li>"+wn._("<b>Cancel</b> allows you change Submitted documents by cancelling them and amending them.")+
		wn._("Cancel permission also allows the user to delete a document (if it is not linked to any other document).")+"</li>\
	<li>"+wn._("When you <b>Amend</b> a document after cancel and save it, it will get a new number that is a version of the old number.")+
		wn._("For example if you cancel and amend 'INV004' it will become a new document 'INV004-1'. This helps you to keep track of each amendment.")+
	"</li>\
	</ol>\
	</tr></td>\
	<tr><td>\
	<h4><i class='icon-signal'></i> "+wn._("Permission Levels")+":</h4>\
	<ol>\
	<li>"+wn._("Permissions at level 0 are 'Document Level' permissions, i.e. they are primary for access to the document.")+
		wn._("If a User does not have access at Level 0, then higher levels are meaningless")+".</li>\
	<li>"+wn._("Permissions at higher levels are 'Field Level' permissions. All Fields have a 'Permission Level' set against them and the rules defined at that permissions apply to the field. This is useful incase you want to hide or make certain field read-only.")+
		wn._("You can use <a href='#Form/Customize Form'>Customize Form</a> to set levels on fields.")+"</li>\
	</ol>\
	</tr></td>\
	<tr><td>\
	<h4><i class='icon-user'></i> "+wn._("Restricting By User")+":</h4>\
	<ol>\
		<li>"+wn._("To restrict a User of a particular Role to documents that are only self-created.")+
			wn._("Click on button in the 'Condition' column and select the option 'User is the creator of the document'")+".</li>\
		<li>"+wn._("To restrict a User of a particular Role to documents that are explicitly assigned to them")+ ":"+
			+ wn._("create a Custom Field of type Link (Profile) and then use the 'Condition' settings to map that field to the Permission rule.")+
	"</ol>\
	</tr></td>\
	<tr><td>\
	<h4><i class='icon-cog'></i> "+wn._("Advanced Settings")+":</h4>\
	<p>"+wn._("To further restrict permissions based on certain values in a document, use the 'Condition' settings.")+" <br><br>"+
		wn._("For example: You want to restrict users to transactions marked with a certain property called 'Territory'")+":</p>\
	<ol>\
		<li>"+wn._("Make sure that the transactions you want to restrict have a Link field 'territory' that maps to a 'Territory' master.")+" "
		+wn._("If not, create a")+
			"<a href='#List/Custom Field'>"+wn._("Custom Field")+"</a>"+ wn._("of type Link")+".</li>\
		<li>"+wn._("In the Permission Manager, click on the button in the 'Condition' column for the Role you want to restrict.")+"</li>\
		<li>"+wn._("A new popup will open that will ask you to select further conditions.")+
			wn._("If the 'territory' Link Field exists, it will give you an option to select it")+".</li>\
		<li>"+wn._("Go to Setup > <a href='#user-properties'>User Properties</a> to set \
			'territory' for diffent Users.")+"</li>\
	</ol>\
	<p>"+wn._("Once you have set this, the users will only be able access documents with that property.")+"</p>\
	<hr>\
	<p>If these instructions where not helpful, please add in your suggestions at\
	<a href='https://github.com/webnotes/wnframework/issues'>GitHub Issues</a></p>\
	</tr></td>\
	</table>");
	wrapper.permission_engine = new wn.PermissionEngine(wrapper);
}
wn.pages['permission-manager'].refresh = function(wrapper) { 
	wrapper.permission_engine.set_from_route();
}

wn.PermissionEngine = Class.extend({
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
		return wn.call({
			module:"core",
			page:"permission_manager",
			method: "get_roles_and_doctypes",
			callback: function(r) {
				me.options = r.message;
				me.doctype_select 
					= me.wrapper.appframe.add_select("doctypes", 
						[wn._("Select Document Type")+"..."].concat(r.message.doctypes))
						.change(function() {
							wn.set_route("permission-manager", $(this).val())
						});
				me.role_select 
					= me.wrapper.appframe.add_select("roles", 
						[wn._("Select Role")+"..."].concat(r.message.roles))
						.change(function() {
							me.refresh();
						});
				me.set_from_route();
			}
		});
	},
	set_from_route: function() {
		if(wn.get_route()[1] && this.doctype_select) {
			this.doctype_select.val(wn.get_route()[1]);
			this.refresh();
		} else {
			this.refresh();
		}
	},
	make_reset_button: function() {
		var me = this;
		me.reset_button = me.wrapper.appframe.add_button("Reset Permissions", function() {
			if(wn.confirm("Reset Permissions for " + me.get_doctype() + "?", function() {
					return wn.call({
						module:"core",
						page:"permission_manager",
						method:"reset",
						args: {
							doctype:me.get_doctype(),
						},
						callback: function() { me.refresh(); }
					});
				}));
			}, 'icon-retweet').toggle(false);
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
			this.body.html("<div class='alert alert-info'>"+wn._("Select Document Type or Role to start.")+"</div>");
			return;
		}
		// get permissions
		wn.call({
			module: "core",
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
		me.reset_button.toggle(me.get_doctype() ? true : false);
	},
	render: function(perm_list) {
		this.body.empty();
		this.perm_list = perm_list;
		if(!perm_list.length) {
			this.body.html("<div class='alert alert-warning'>"+wn._("No Permissions set for this criteria.")+"</div>");
		} else {
			this.show_permission_table(perm_list);
		}
		this.show_add_rule();
	},
	show_permission_table: function(perm_list) {
		var me = this;
		this.table = $("<table class='table table-bordered'>\
			<thead><tr></tr></thead>\
			<tbody></tbody>\
		</table>").appendTo(this.body);
		
		$.each([["Document Type", 150], ["Role", 100], ["Level",50], 
			["Read", 50], ["Edit", 50], ["Make New", 50], 
			["Submit", 50], ["Cancel", 50], ["Amend", 50], ["Report", 50], 
			["Condition", 150], ["", 50]], function(i, col) {
			$("<th>").html(col[0]).css("width", col[1]+"px")
				.appendTo(me.table.find("thead tr"));
		});

		var add_cell = function(row, d, fieldname, is_check) {
			var cell = $("<td>").appendTo(row).attr("data-fieldname", fieldname);
			if(is_check) {
				if(d.permlevel > 0 && ["read", "write"].indexOf(fieldname)==-1) {
					cell.html("-");
				} else {
					var input = $("<input type='checkbox'>")
						.prop("checked", d[fieldname] ? true: false)
						.attr("data-ptype", fieldname)
						.attr("data-name", d.name)
						.attr("data-doctype", d.parent)
						.appendTo(cell);
				}
			} else {
				cell.html(d[fieldname]);
			}
			return cell;
		}
				
		$.each(perm_list, function(i, d) {
			if(!d.permlevel) d.permlevel = 0;
			var row = $("<tr>").appendTo(me.table.find("tbody"));
			add_cell(row, d, "parent");
			me.set_show_users(add_cell(row, d, "role"), d.role);
			
			var cell = add_cell(row, d, "permlevel");
			if(d.permlevel==0) {
				cell.css("font-weight", "bold");
				row.addClass("warning");
			}
			add_cell(row, d, "read", true);
			add_cell(row, d, "write", true);
			add_cell(row, d, "create", true);
			add_cell(row, d, "submit", true);
			add_cell(row, d, "cancel", true);
			add_cell(row, d, "amend", true);
			add_cell(row, d, "report", true);
						
			// buttons
			me.add_match_button(row, d);
			me.add_delete_button(row, d);
		});
	},
	set_show_users: function(cell, role) {
		cell.html("<a href='#'>"+role+"</a>")
			.find("a")
			.attr("data-role", role)
			.click(function() {
				var role = $(this).attr("data-role");
				wn.call({
					module: "core",
					page: "permission_manager",
					method: "get_users_with_role",
					args: {
						role: role
					},
					callback: function(r) {
						r.message = $.map(r.message, function(p) {
							return '<a href="#Form/Profile/'+p+'">'+p+'</a>';
						})
						msgprint("<h4>Users with role "+role+":</h4>" 
							+ r.message.join("<br>"));
					}
				})
				return false;
			})
	},
	add_match_button: function(row, d) {
		var me = this;
		if(d.permlevel > 0) {
			$("<td>-</td>").appendTo(row);
			return;
		}
		var btn = $("<button class='btn btn-default btn-small'></button>")
			.html(d.match ? d.match : wn._("For All Users"))
			.appendTo($("<td>").appendTo(row))
			.attr("data-name", d.name)
			.click(function() {
				me.show_match_manager($(this).attr("data-name"));
			});
		if(d.match) btn.addClass("btn-info");
	},
	add_delete_button: function(row, d) {
		var me = this;
		$("<button class='btn btn-default btn-small'><i class='icon-remove'></i></button>")
			.appendTo($("<td>").appendTo(row))
			.attr("data-name", d.name)
			.attr("data-doctype", d.parent)
			.click(function() {
				return wn.call({
					module: "core",
					page: "permission_manager",
					method: "remove",
					args: {
						name: $(this).attr("data-name"),
						doctype: $(this).attr("data-doctype")
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
	add_check_events: function() {
		var me = this;
		this.body.on("click", "input[type='checkbox']", function() {
			var chk = $(this);
			var args = {
				name: chk.attr("data-name"),
				doctype: chk.attr("data-doctype"),
				ptype: chk.attr("data-ptype"),
				value: chk.prop("checked") ? 1 : 0
			}
			return wn.call({
				module: "core",
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
		$("<button class='btn btn-default btn-info'>"+wn._("Add A New Rule")+"</button>")
			.appendTo($("<p>").appendTo(this.body))
			.click(function() {
				var d = new wn.ui.Dialog({
					title: wn._("Add New Permission Rule"),
					fields: [
						{fieldtype:"Select", label:"Document Type",
							options:me.options.doctypes, reqd:1, fieldname:"parent"},
						{fieldtype:"Select", label:"Role",
							options:me.options.roles, reqd:1},
						{fieldtype:"Select", label:"Permission Level",
							options:[0,1,2,3,4,5,6,7,8,9], reqd:1, fieldname: "permlevel",
							description: wn._("Level 0 is for document level permissions, higher levels for field level permissions.")},
						{fieldtype:"Button", label:"Add"},
					]
				});
				if(me.get_doctype()) {
					d.set_value("parent", me.get_doctype());
					d.get_input("parent").attr("disabled", true);
				}
				if(me.get_role()) {
					d.set_value("role", me.get_role());
					d.get_input("role").attr("disabled", true);
				}
				d.set_value("permlevel", "0");
				d.get_input("add").click(function() {
					var args = d.get_values();
					if(!args) {
						return;
					}
					wn.call({
						module: "core",
						page: "permission_manager",
						method: "add",
						args: args,
						callback: function(r) {
							if(r.exc) {
								msgprint(wn._("Did not add."));
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
	get_perm: function(name) {
		return $.map(this.perm_list, function(d) { if(d.name==name) return d; })[0];		
	},
	show_match_manager:function(name) {
		var perm = this.get_perm(name);
		var me = this;
		
		wn.model.with_doctype(perm.parent, function() {
			var dialog = new wn.ui.Dialog({
				title: "Applies for Users",
			});
			$(dialog.body).html("<h4>Rule Applies to Following Users:</h4>\
			<label class='radio'>\
			<input name='perm-rule' type='radio' value=''> All users with role <b>"+perm.role+"</b>.\
			</label>\
			<label class='radio'>\
			<input name='perm-rule' type='radio' value='owner'> The user is the creator of the document.\
			</label>").css("padding", "15px");

			// profile fields
			$.each(me.get_profile_fields(perm.parent), function(i, d) {
				$("<label class='radio'>\
				<input name='perm-rule' type='radio' value='"+d.fieldname
					+":user'>Value of field <b>"+d.label+"</b> is the User.\
				</label>").appendTo(dialog.body);
			});

			// add options for all link fields
			$.each(me.get_link_fields(perm.parent), function(i, d) {
				$("<label class='radio'>\
				<input name='perm-rule' type='radio' value='"+d.fieldname
					+"'><b>"+d.label+"</b> in <b>"+d.parent+"</b> matches <a href='#user-properties//"+d.fieldname+"'>User Property</a> <b>"
					+d.fieldname+"</b>.\
				</label>").appendTo(dialog.body);
			});
			
			// button
			$("<button class='btn btn-default btn-info'>Update</button>")
				.appendTo($("<p>").appendTo(dialog.body))
				.attr("data-name", perm.name)
				.click(function() {
					var match_value = $(dialog.wrapper).find(":radio:checked").val();
					var perm = me.get_perm($(this).attr('data-name'))
					return wn.call({
						module: "core",
						page: "permission_manager",
						method: "update_match",
						args: {
							name: perm.name,
							doctype: perm.parent,
							match: match_value
						},
						callback: function() {
							dialog.hide();
							me.refresh();
						}
					})
				});
			dialog.show();
			
			// select
			if(perm.match) {
				$(dialog.wrapper).find("[value='"+perm.match+"']").prop("checked", true).focus();
			} else {
				$(dialog.wrapper).find('[value=""]').prop("checked", true).focus();
			}
		});
	},
	get_profile_fields: function(doctype) {
		var profile_fields = wn.model.get("DocField", {parent:doctype, 
			fieldtype:"Link", options:"Profile"});
		
		profile_fields = profile_fields.concat(wn.model.get("DocField", {parent:doctype, 
				fieldtype:"Select", link_doctype:"Profile"}))
		
		return 	profile_fields	
	},
	get_link_fields: function(doctype) {
		return link_fields = wn.model.get("DocField", {parent:doctype, 
			fieldtype:"Link", options:["not in", ["Profile", '[Select]']]});
	}
})