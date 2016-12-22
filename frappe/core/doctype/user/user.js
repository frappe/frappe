frappe.ui.form.on('User', {
	before_load: function(frm) {
		var update_tz_select = function(user_language) {
			frm.set_df_property("time_zone", "options", [""].concat(frappe.all_timezones));
		}

		if(!frappe.all_timezones) {
			frappe.call({
				method: "frappe.core.doctype.user.user.get_timezones",
				callback: function(r) {
					frappe.all_timezones = r.message.timezones;
					update_tz_select();
				}
			});
		} else {
			update_tz_select();
		}

	},
	onload: function(frm) {
		if(has_common(user_roles, ["Administrator", "System Manager"]) && !frm.doc.__islocal) {
			if(!frm.roles_editor) {
				var role_area = $('<div style="min-height: 300px">')
					.appendTo(frm.fields_dict.roles_html.wrapper);
				frm.roles_editor = new frappe.RoleEditor(role_area);

				var module_area = $('<div style="min-height: 300px">')
					.appendTo(frm.fields_dict.modules_html.wrapper);
				frm.module_editor = new frappe.ModuleEditor(frm, module_area)
			} else {
				frm.roles_editor.show();
			}
		}
	},
	refresh: function(frm) {
		var doc = frm.doc;

		if(doc.name===user && !doc.__unsaved
			&& frappe.all_timezones
			&& (doc.language || frappe.boot.user.language)
			&& doc.language !== frappe.boot.user.language) {
			msgprint(__("Refreshing..."));
			window.location.reload();
		}

		frm.toggle_display(['sb1', 'sb3', 'modules_access'], false);

		if(!doc.__islocal){
			frm.add_custom_button(__("Set Desktop Icons"), function() {
				frappe.route_options = {
					"user": doc.name
				};
				frappe.set_route("modules_setup");
			}, null, "btn-default")

			if(has_common(user_roles, ["Administrator", "System Manager"])) {

				frm.add_custom_button(__("Set User Permissions"), function() {
					frappe.route_options = {
						"user": doc.name
					};
					frappe.set_route("user-permissions");
				}, null, "btn-default")

				frm.toggle_display(['sb1', 'sb3', 'modules_access'], true);
			}
			frm.trigger('enabled');

			frm.roles_editor && frm.roles_editor.show();
			frm.module_editor && frm.module_editor.refresh();

			if(user==doc.name) {
				// update display settings
				if(doc.user_image) {
					frappe.boot.user_info[user].image = frappe.utils.get_file_link(doc.user_image);
				}
			}
		}
		if (frm.doc.user_emails){
			var found =0
			for (var i = 0;i<frm.doc.user_emails.length;i++){
				if (frm.doc.email==frm.doc.user_emails[i].email_id){
					found = 1;
				}
			}
			frm.get_field("create_user_email").df.hidden = found;
			frm.refresh_field("create_user_email");
		}else{
			frm.get_field("create_user_email").df.hidden = 1
		}
		frm.refresh_field("create_user_email");

		if (frappe.route_titles["unsaved"]===1){
			delete frappe.route_titles["unsaved"];
			for ( var i=0;i<frm.doc.user_emails.length;i++){
				frm.doc.user_emails[i].idx=frm.doc.user_emails[i].idx+1;
			}
			frm.doc.email_account
		cur_frm.dirty();
		}
	},
	validate: function(frm) {
		if(frm.roles_editor) {
			frm.roles_editor.set_roles_in_table()
		}
	},
	enabled: function(frm) {
		var doc = frm.doc;
		if(!doc.__islocal && has_common(user_roles, ["Administrator", "System Manager"])) {
			frm.toggle_display(['sb1', 'sb3', 'modules_access'], doc.enabled);
			frm.set_df_property('enabled', 'read_only', 0);
		}

		if(user!="Administrator") {
			frm.toggle_enable('email', doc.__islocal);
		}
	},
	create_user_email:function(frm) {
		frappe.call({
			method: 'frappe.core.doctype.user.user.has_email_account',
			args: {email:cur_frm.doc.email},
			callback: function(r) {
				if (r["message"]== undefined){
					frappe.route_options = {
						"email_id": cur_frm.doc.email,
						"awaiting_password":1,
						"enable_incoming":1,
						"append_to":"Communication"
					};
					frappe.model.with_doctype("Email Account", function (doc) {
						var doc = frappe.model.get_new_doc("Email Account");
					frappe.route_titles["create user account"]=cur_frm.doc.name;
					frappe.set_route("Form", "Email Account", doc.name);
					})
				}else{
					frappe.route_titles["create user account"]=cur_frm.doc.name;					
					frappe.set_route("Form", "Email Account", r["message"][0]["name"]);
				}
			}
		})
	}
})


frappe.ModuleEditor = Class.extend({
	init: function(frm, wrapper) {
		this.wrapper = $('<div class="row module-block-list"></div>').appendTo(wrapper);
		this.frm = frm;
		this.make();
	},
	make: function() {
		var me = this;
		this.frm.doc.__onload.all_modules.forEach(function(m) {
			$(repl('<div class="col-sm-6"><div class="checkbox">\
				<label><input type="checkbox" class="block-module-check" data-module="%(module)s">\
				%(module)s</label></div></div>', {module: m})).appendTo(me.wrapper);
		});
		this.bind();
	},
	refresh: function() {
		var me = this;
		this.wrapper.find(".block-module-check").prop("checked", true);
		$.each(this.frm.doc.block_modules, function(i, d) {
			me.wrapper.find(".block-module-check[data-module='"+ d.module +"']").prop("checked", false);
		});
	},
	bind: function() {
		this.wrapper.on("change", ".block-module-check", function() {
			var module = $(this).attr('data-module');
			if($(this).prop("checked")) {
				// remove from block_modules
				me.frm.doc.block_modules = $.map(me.frm.doc.block_modules || [], function(d) { if(d.module != module){ return d } });
			} else {
				me.frm.add_child("block_modules", {"module": module});
			}
		});
	}
})

frappe.RoleEditor = Class.extend({
	init: function(wrapper) {
		var me = this;
		this.wrapper = wrapper;
		$(wrapper).html('<div class="help">' + __("Loading") + '...</div>')
		return frappe.call({
			method: 'frappe.core.doctype.user.user.get_all_roles',
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
		var role_toolbar = $('<p><button class="btn btn-default btn-add btn-sm" style="margin-right: 5px;"></button>\
			<button class="btn btn-sm btn-default btn-remove"></button></p>').appendTo($(this.wrapper));

		role_toolbar.find(".btn-add")
			.html(__('Add all roles'))
			.on("click", function() {
			$(me.wrapper).find('input[type="checkbox"]').each(function(i, check) {
				if(!$(check).is(":checked")) {
					check.checked = true;
				}
			});
		});

		role_toolbar.find(".btn-remove")
			.html(__('Clear all roles'))
			.on("click", function() {
			$(me.wrapper).find('input[type="checkbox"]').each(function(i, check) {
				if($(check).is(":checked")) {
					check.checked = false;
				}
			});
		});

		$.each(this.roles, function(i, role) {
			$(me.wrapper).append(repl('<div class="user-role" \
				data-user-role="%(role_value)s">\
				<input type="checkbox" style="margin-top:0px;"> \
				<a href="#" class="grey">%(role_display)s</a>\
			</div>', {role_value: role,role_display:__(role)}));
		});

		$(this.wrapper).find('input[type="checkbox"]').change(function() {
			me.set_roles_in_table();
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
		$.each((cur_frm.doc.user_roles || []), function(i, user_role) {
				var checkbox = $(me.wrapper)
					.find('[data-user-role="'+user_role.role+'"] input[type="checkbox"]').get(0);
				if(checkbox) checkbox.checked = true;
			});
	},
	set_roles_in_table: function() {
		var opts = this.get_roles();
		var existing_roles_map = {};
		var existing_roles_list = [];

		$.each((cur_frm.doc.user_roles || []), function(i, user_role) {
				existing_roles_map[user_role.role] = user_role.name;
				existing_roles_list.push(user_role.role);
			});

		// remove unchecked roles
		$.each(opts.unchecked_roles, function(i, role) {
			if(existing_roles_list.indexOf(role)!=-1) {
				frappe.model.clear_doc("UserRole", existing_roles_map[role]);
			}
		});

		// add new roles that are checked
		$.each(opts.checked_roles, function(i, role) {
			if(existing_roles_list.indexOf(role)==-1) {
				var user_role = frappe.model.add_child(cur_frm.doc, "UserRole", "user_roles");
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
		return frappe.call({
			method: 'frappe.core.doctype.user.user.get_perm_info',
			args: {role: role},
			callback: function(r) {
				var $body = $(me.perm_dialog.body);
				// TODO fix the overflow issue and also display perms like report, import, etc.

				$body.append('<table class="user-perm"><thead><tr>'
					+ '<th style="text-align: left">' + __('Document Type') + '</th>'
					+ '<th>' + __('Level') + '</th>'
					+ '<th>' + __('Apply User Permissions') + '</th>'
					+ '<th>' + __('Read') + '</th>'
					+ '<th>' + __('Write') + '</th>'
					+ '<th>' + __('Create') + '</th>'
					+ '<th>' + __('Delete') + '</th>'
					+ '<th>' + __('Submit') + '</th>'
					+ '<th>' + __('Cancel') + '</th>'
					+ '<th>' + __('Amend') + '</th>'
					// + '<th>' + __('Report') + '</th>'
					// + '<th>' + __('Import') + '</th>'
					// + '<th>' + __('Export') + '</th>'
					// + '<th>' + __('Print') + '</th>'
					// + '<th>' + __('Email') + '</th>'
					+ '<th>' + __('Set User Permissions') + '</th>'
					+ '</tr></thead><tbody></tbody></table>');

				for(var i=0, l=r.message.length; i<l; i++) {
					var perm = r.message[i];

					// if permission -> icon
					for(key in perm) {
						if(key!='parent' && key!='permlevel') {
							if(perm[key]) {
								perm[key] = '<i class="fa fa-check"></i>';
							} else {
								perm[key] = '';
							}
						}
					}

					$body.find('tbody').append(repl('<tr>\
						<td style="text-align: left">%(parent)s</td>\
						<td>%(permlevel)s</td>\
						<td>%(apply_user_permissions)s</td>\
						<td>%(read)s</td>\
						<td>%(write)s</td>\
						<td>%(create)s</td>\
						<td>%(delete)s</td>\
						<td>%(submit)s</td>\
						<td>%(cancel)s</td>\
						<td>%(amend)s</td>'
						// + '<td>%(report)s</td>\
						// <td>%(import)s</td>\
						// <td>%(export)s</td>\
						// <td>%(print)s</td>\
						// <td>%(email)s</td>'
						+ '<td>%(set_user_permissions)s</td>\
						</tr>', perm))
				}

				me.perm_dialog.show();
			}
		});

	},
	make_perm_dialog: function() {
		this.perm_dialog = new frappe.ui.Dialog({
			title:__('Role Permissions')
		});

		this.perm_dialog.$wrapper.find('.modal-dialog').css("width", "800px");
	}
});
