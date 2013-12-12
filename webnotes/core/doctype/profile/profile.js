cur_frm.cscript.onload = function(doc, dt, dn, callback) {
	if(has_common(user_roles, ["Administrator", "System Manager"])) {
		if(!cur_frm.roles_editor) {
			var role_area = $('<div style="min-height: 300px">')
				.appendTo(cur_frm.fields_dict.roles_html.wrapper);
			cur_frm.roles_editor = new wn.RoleEditor(role_area);
		} else {
			cur_frm.roles_editor.show();
		}
	}
}

cur_frm.cscript.before_load = function(doc, dt, dn, callback) {
	wn.provide("wn.langauges");
	
	var update_language_select = function() {
		cur_frm.set_df_property("language", "options", wn.languages || ["", "English"]);
		callback();
	}
	
	if(!wn.languages) {
		wn.call({
			method: "webnotes.core.doctype.profile.profile.get_languages",
			callback: function(r) {
				wn.languages = r.message;
				update_language_select();
			}
		})
	} else {
		update_language_select();
	}
}

cur_frm.cscript.user_image = function(doc) {
	refresh_field("user_image_show");
}

cur_frm.cscript.refresh = function(doc) {
	cur_frm.toggle_display('change_password', !doc.__islocal);

	cur_frm.toggle_display(['sb1', 'sb3'], false);

 	if(!doc.__islocal){		
		cur_frm.add_custom_button("Set Properties", function() {
			wn.set_route("user-properties", doc.name);
		})

		if(has_common(user_roles, ["Administrator", "System Manager"])) {
			cur_frm.toggle_display(['sb1', 'sb3'], true);
		}
		cur_frm.cscript.enabled(doc);
		
		cur_frm.roles_editor && cur_frm.roles_editor.show();
		
		if(user==doc.name) {
			// update display settings
			if(doc.background_image) {
				wn.ui.set_user_background(doc.background_image);
			}
			if(doc.user_image) {
				wn.boot.user_info[user].image = wn.utils.get_file_link(doc.user_image);
			}
		}
	}
}

cur_frm.cscript.enabled = function(doc) {
	if(!doc.__islocal && has_common(user_roles, ["Administrator", "System Manager"])) {
		cur_frm.toggle_display(['sb1', 'sb3'], doc.enabled);	
		cur_frm.toggle_enable('*', doc.enabled);
		cur_frm.set_df_property('enabled', 'read_only', 0);
	}
	
	if(user!="Administrator") {
		cur_frm.toggle_enable('email', doc.__islocal);
	}
}

cur_frm.cscript.validate = function(doc) {
	if(cur_frm.roles_editor) {
		cur_frm.roles_editor.set_roles_in_table()
	}
}

wn.RoleEditor = Class.extend({
	init: function(wrapper) {
		var me = this;
		this.wrapper = wrapper;
		$(wrapper).html('<div class="help">Loading...</div>')
		return wn.call({
			method: 'webnotes.core.doctype.profile.profile.get_all_roles',
			callback: function(r) {
				me.roles = r.message;
				me.show_roles();
				
				// refresh call could've already happened 
				// when all role checkboxes weren't created
				if(cur_frm.doc) {
					cur_frm.roles_editor.show();
				}
			}
		});
	},
	show_roles: function() {
		var me = this;
		$(this.wrapper).empty();
		var add_all_roles = $('<p><button class="btn btn-default btn-add">Add all roles</button>\
			<button class="btn btn-default btn-remove">Clear all roles</button></p>').appendTo($(this.wrapper));
		add_all_roles.find(".btn-add").on("click", function() {
			$(me.wrapper).find('input[type="checkbox"]').each(function(i, check) {
				if(!$(check).is(":checked")) {
					check.checked = true;
				}
			});
		});

		add_all_roles.find(".btn-remove").on("click", function() {
			$(me.wrapper).find('input[type="checkbox"]').each(function(i, check) {
				if($(check).is(":checked")) {
					check.checked = false;
				}
			});
		});
		
		for(var i in this.roles) {
			$(this.wrapper).append(repl('<div class="user-role" \
				data-user-role="%(role)s">\
				<input type="checkbox" style="margin-top:0px;"> \
				<a href="#">%(role)s</a>\
			</div>', {role: this.roles[i]}));
		}
		$(this.wrapper).find('input[type="checkbox"]').change(function() {
			cur_frm.dirty();
		});
		$(this.wrapper).find('.user-role a').click(function() {
			me.show_permissions($(this).parent().attr('data-user-role'))
			return false;
		});
	},
	show: function() {
		var me = this;
		
		// uncheck all roles
		$(this.wrapper).find('input[type="checkbox"]')
			.each(function(i, checkbox) { checkbox.checked = false; });
		
		// set user roles as checked
		$.each(wn.model.get("UserRole", {parent: cur_frm.doc.name, 
			parentfield: "user_roles"}), function(i, user_role) {
				var checkbox = $(me.wrapper)
					.find('[data-user-role="'+user_role.role+'"] input[type="checkbox"]').get(0);
				if(checkbox) checkbox.checked = true;
			});
	},
	set_roles_in_table: function() {
		var opts = this.get_roles();
		var existing_roles_map = {};
		var existing_roles_list = [];
		
		$.each(wn.model.get("UserRole", {parent: cur_frm.doc.name, 
			parentfield: "user_roles"}), function(i, user_role) { 
				existing_roles_map[user_role.role] = user_role.name;
				existing_roles_list.push(user_role.role);
			});
		
		// remove unchecked roles
		$.each(opts.unchecked_roles, function(i, role) {
			if(existing_roles_list.indexOf(role)!=-1) {
				wn.model.clear_doc("UserRole", existing_roles_map[role]);
			}
		});
		
		// add new roles that are checked
		$.each(opts.checked_roles, function(i, role) {
			if(existing_roles_list.indexOf(role)==-1) {
				var user_role = wn.model.add_child(cur_frm.doc, "UserRole", "user_roles");
				user_role.role = role;
			}
		});
		
		refresh_field("user_roles");
	},	
	get_roles: function() {
		var checked_roles = [];
		var unchecked_roles = [];
		$(this.wrapper).find('[data-user-role]').each(function() {
			if($(this).find('input[type="checkbox"]:checked').length) {
				checked_roles.push($(this).attr('data-user-role'));
			} else {
				unchecked_roles.push($(this).attr('data-user-role'));
			}
		});
		
		return {
			checked_roles: checked_roles,
			unchecked_roles: unchecked_roles
		}
	},
	show_permissions: function(role) {
		// show permissions for a role
		var me = this;
		if(!this.perm_dialog)
			this.make_perm_dialog()
		$(this.perm_dialog.body).empty();
		return wn.call({
			method: 'webnotes.core.doctype.profile.profile.get_perm_info',
			args: {role: role},
			callback: function(r) {
				var $body = $(me.perm_dialog.body);
				$body.append('<table class="user-perm"><tbody><tr>\
					<th style="text-align: left">Document Type</th>\
					<th>Level</th>\
					<th>Read</th>\
					<th>Write</th>\
					<th>Submit</th>\
					<th>Cancel</th>\
					<th>Amend</th></tr></tbody></table>');
				for(var i in r.message) {
					var perm = r.message[i];
					
					// if permission -> icon
					for(key in perm) {
						if(key!='parent' && key!='permlevel') {
							if(perm[key]) {
								perm[key] = '<i class="icon-ok"></i>';
							} else {
								perm[key] = '';
							}							
						}
					}
					
					$body.find('tbody').append(repl('<tr>\
						<td style="text-align: left">%(parent)s</td>\
						<td>%(permlevel)s</td>\
						<td>%(read)s</td>\
						<td>%(write)s</td>\
						<td>%(submit)s</td>\
						<td>%(cancel)s</td>\
						<td>%(amend)s</td>\
						</tr>', perm))
				}
				
				me.perm_dialog.show();
			}
		});
		
	},
	make_perm_dialog: function() {
		this.perm_dialog = new wn.ui.Dialog({
			title:'Role Permissions',
			width: 500
		});
	}
});


