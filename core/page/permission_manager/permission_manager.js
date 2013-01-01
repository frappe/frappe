wn.pages['permission-manager'].onload = function(wrapper) { 
	wn.ui.make_app_page({
		parent: wrapper,
		title: 'Permission Manager',
		single_column: true
	});
	wrapper.permission_engine = new wn.PermissionEngine(wrapper);
}
wn.pages['permission-manager'].refresh = function(wrapper) { 
	wrapper.permission_engine.set_from_route();
}

wn.PermissionEngine = Class.extend({
	init: function(wrapper) {
		this.wrapper = wrapper;
		this.body = $(this.wrapper).find(".layout-main");
		this.make();
		this.refresh();
		this.add_check_events();
	},
	make: function() {
		var me = this;
		
		me.make_reset_button();
		wn.call({
			module:"core",
			page:"permission_manager",
			method: "get_roles_and_doctypes",
			callback: function(r) {
				me.options = r.message;
				me.doctype_select 
					= me.wrapper.appframe.add_select("doctypes", 
						["Select Document Type..."].concat(r.message.doctypes))
						.css("width", "200px")
						.change(function() {
							wn.set_route("permission-manager", $(this).val())
						});
				me.role_select 
					= me.wrapper.appframe.add_select("roles", 
						["Select Role..."].concat(r.message.roles))
						.css("width", "200px")
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
					wn.call({
						module:"core",
						page:"permission_manager",
						method:"reset",
						args: {
							doctype:me.get_doctype(),
						},
						callback: function() { me.refresh(); }
					});
				}));
			}, 'icon-retweet');
	},
	get_doctype: function() {
		var doctype = this.doctype_select.val();
		return doctype=="Select Document Type..." ? null : doctype;
	},
	get_role: function() {
		var role = this.role_select.val();
		return role=="Select Role..." ? null : role;
	},
	refresh: function() {
		var me = this;
		if(!me.doctype_select) {
			this.body.html("<div class='alert'>Loading...</div>");
			return;
		}
		if(!me.get_doctype() && !me.get_role()) {
			this.body.html("<div class='alert'>Select Document Type or Role to start.</div>");
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
			this.body.html("<div class='alert'>No Permissions set for this criteria.</div>");
		} else {
			this.show_permission_table(perm_list);
		}
		this.show_add_rule();
		this.show_explain();
	},
	show_permission_table: function(perm_list) {
		var me = this;
		this.table = $("<table class='table table-bordered'>\
			<thead><tr></tr></thead>\
			<tbody></tbody>\
		</table>").appendTo(this.body);
		
		$.each([["Document Type", 150], ["Role", 100], ["Level",50], 
			["Read", 50], ["Write", 50], ["Create", 50], 
			["Submit", 50], ["Cancel", 50], ["Amend", 50], 
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
						.attr("checked", d[fieldname] ? "checked": null)
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
			add_cell(row, d, "role");
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
						
			// buttons
			me.add_match_button(row, d);
			me.add_delete_button(row, d);
		});
	},
	add_match_button: function(row, d) {
		var me = this;
		if(d.permlevel > 0) {
			$("<td>-</td>").appendTo(row);
			return;
		}
		var btn = $("<button class='btn btn-small'></button>")
			.html(d.match ? d.match : "For All Users")
			.appendTo($("<td>").appendTo(row))
			.attr("data-name", d.name)
			.click(function() {
				me.show_match_manager($(this).attr("data-name"));
			});
		if(d.match) btn.addClass("btn-inverse");
	},
	add_delete_button: function(row, d) {
		var me = this;
		$("<button class='btn btn-small'><i class='icon-remove'></i></button>")
			.appendTo($("<td>").appendTo(row))
			.attr("data-name", d.name)
			.attr("data-doctype", d.parent)
			.click(function() {
				wn.call({
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
				value: chk.is(":checked") ? 1 : 0
			}
			wn.call({
				module: "core",
				page: "permission_manager",
				method: "update",
				args: args,
				callback: function(r) {
					if(r.exc) {
						// exception: reverse
						chk.attr("checked", chk.is(":checked") ? null : "checked");
					} else {
						me.get_perm(args.name)[args.ptype]=args.value; 
						me.show_explain();
					}
				}
			})
		})
	},
	show_add_rule: function() {
		var me = this;
		$("<button class='btn btn-info'>Add A New Rule</button>")
			.appendTo($("<p>").appendTo(this.body))
			.click(function() {
				var d = new wn.ui.Dialog({
					title: "Add New Permission Rule",
					fields: [
						{fieldtype:"Select", label:"Document Type",
							options:me.options.doctypes, reqd:1, fieldname:"parent"},
						{fieldtype:"Select", label:"Role",
							options:me.options.roles, reqd:1},
						{fieldtype:"Select", label:"Permission Level",
							options:[0,1,2,3,4,5,6,7,8,9], reqd:1, fieldname: "permlevel",
							description:"Level 0 is for document level permissions, higher levels for field level permissions."},
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
					+"'><b>"+d.label+"</b> in <b>"+d.parent+"</b> matches <a href='#user-properties'>User Property</a> <b>"
					+d.fieldname+"</b>.\
				</label>").appendTo(dialog.body);
			});
			
			// button
			$("<button class='btn btn-info'>Update</button>")
				.appendTo($("<p>").appendTo(dialog.body))
				.attr("data-name", perm.name)
				.click(function() {
					var match_value = $(dialog.wrapper).find(":radio:checked").val();
					var perm = me.get_perm($(this).attr('data-name'))
					wn.call({
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
				$(dialog.wrapper).find("[value='"+perm.match+"']").attr("checked", "checked").focus();
			} else {
				$(dialog.wrapper).find('[value=""]').attr("checked", "checked").focus();
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
	},
	show_explain: function() {
		$(".perm-explain").remove();
		if(!this.get_doctype()) return;
		var wrapper = $("<div class='perm-explain well'></div>").appendTo(this.body);
		var doctype = null;
		var core_finished = false;
		$.each(this.perm_list, function(i, p) {
			if(p.parent != doctype) {
				core_finished = false;
				doctype = p.parent;
				$('<h3>For ' + doctype + '</h3><h4>Document Permissions</h4>')
					.appendTo(wrapper);
				
			}

			if(p.permlevel==0) {
				var perms = $.map(["read", "write", "create", "submit", "cancel", "amend"], function(type) {
					if(p[type]) return type;
				}).join(", ");
				if(!p.match) {
					var _p = $('<p>').html("A user with role <b>"+p.role + "</b> can " 
						+ perms + " a document of type <b>" + doctype + "</b>.")
					
				} else {
					if(p.match=="owner") {
						var _p = $('<p>').html("A user with role <b>"+p.role + "</b> can " 
							+ perms + " <b>" + doctype + "</b> <u>only if</u> that document is created by that user.");
					} else if(p.match.indexOf(":")!=-1) {
						var field = p.match.split(":")[0];
						var _p = $('<p>').html("A user with role <b>"+p.role + "</b> can " 
							+ perms + " <b>" + doctype + "</b> <u>only if</u> <b>"+field+"</b> equals User's Id.");
					} else {
						var _p = $('<p>').html("A user with role <b>"+p.role + "</b> can " 
							+ perms + " <b>" + doctype + "</b> <u>only for</u> records with user's <b>"+p.match+"</b> property.");
					}
				}

			} else {
				if(!core_finished) {
					core_finished = true;
					$("<br><h4>Field Level Permissions</h4>").appendTo(wrapper);
				}
				var perms = $.map(["read", "write"], function(type) {
					if(p[type]) return type;
				}).join(", ");
				var _p = $('<p>').html("A user with role <b>"+p.role + "</b> can only <u>" 
					+ perms + "</u> fields at level <b>"+ p.permlevel +"</b> in a <b>" + doctype + "</b>.")
			}

			$("<a>Show Users</a>").appendTo(_p).attr("data-role", p.role)
				.css("margin-left", "7px")
				.click(function() {
					var link = $(this);
					wn.call({
						module: "core",
						page: "permission_manager",
						method: "get_users_with_role",
						args: {
							role: link.attr("data-role"),
						},
						callback: function(r) {
							$.each(r.message, function(i, uid) {
								msgprint("<a href='#Form/Profile/"+uid+"'>" 
									+ wn.user_info(uid).fullname + "</a> ("+
									uid+")");
							});
							cur_dialog.set_title("Users with role " 
								+ link.attr("data-role"));
						}
					});
				});
			_p.appendTo(wrapper);	
		})
	}
})