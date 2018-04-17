frappe.RoleEditor = Class.extend({
	init: function(wrapper, frm, disable) {
		var me = this;
		this.frm = frm;
		this.wrapper = wrapper;
		this.disable = disable;
		$(wrapper).html('<div class="help">' + __("Loading") + '...</div>');
		frappe.call({
			method: 'frappe.core.doctype.user.user.get_all_roles',
			callback: function(r) {
				me.roles = r.message;
				me.show_roles();

				// refresh call could've already happened
				// when all role checkboxes weren't created
				if(me.frm.doc) {
					me.frm.roles_editor.show();
				}
			}
		});
	},
	show_roles: function() {
		var me = this;
		$(this.wrapper).empty();
		if(me.frm.doctype != 'User') {
			var role_toolbar = $('<p><button class="btn btn-default btn-add btn-sm" style="margin-right: 5px;"></button>\
				<button class="btn btn-sm btn-default btn-remove"></button></p>').appendTo($(this.wrapper));

			role_toolbar.find(".btn-add")
				.html(__('Add all roles'))
				.on("click", function() {
					$(me.wrapper).find('input[type="checkbox"]').each(function(i, check) {
						if (!$(check).is(":checked")) {
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
		}

		$.each(this.roles, function(i, role) {
			$(me.wrapper).append(repl('<div class="user-role" \
				data-user-role="%(role_value)s">\
				<input type="checkbox" style="margin-top:0px;" class="box"> \
				<a href="#" class="grey role">%(role_display)s</a>\
			</div>', {role_value: role,role_display:__(role)}));
		});

		$(this.wrapper).find('input[type="checkbox"]').change(function() {
			me.set_roles_in_table();
			me.frm.dirty();
		});
		$(this.wrapper).find('.user-role a').click(function() {
			me.show_permissions($(this).parent().attr('data-user-role'));
			return false;
		});
	},
	show: function() {
		var me = this;
		$('.box').attr('disabled', this.disable);

		// uncheck all roles
		$(this.wrapper).find('input[type="checkbox"]')
			.each(function(i, checkbox) {
				checkbox.checked = false;
			});

		// set user roles as checked
		$.each((me.frm.doc.roles || []), function(i, user_role) {
			var checkbox = $(me.wrapper)
				.find('[data-user-role="'+user_role.role+'"] input[type="checkbox"]').get(0);
			if(checkbox) checkbox.checked = true;
		});

		this.set_enable_disable();
	},
	set_enable_disable: function() {
		$('.box').attr('disabled', this.disable ? true : false);
	},
	set_roles_in_table: function() {
		var opts = this.get_roles();
		var existing_roles_map = {};
		var existing_roles_list = [];
		var me = this;

		$.each((me.frm.doc.roles || []), function(i, user_role) {
			existing_roles_map[user_role.role] = user_role.name;
			existing_roles_list.push(user_role.role);
		});

		// remove unchecked roles
		$.each(opts.unchecked_roles, function(i, role) {
			if(existing_roles_list.indexOf(role)!=-1) {
				frappe.model.clear_doc("Has Role", existing_roles_map[role]);
			}
		});

		// add new roles that are checked
		$.each(opts.checked_roles, function(i, role) {
			if(existing_roles_list.indexOf(role)==-1) {
				var user_role = frappe.model.add_child(me.frm.doc, "Has Role", "roles");
				user_role.role = role;
			}
		});

		refresh_field("roles");
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
		};
	},
	show_permissions: function(role) {
		// show permissions for a role
		var me = this;
		if(!this.perm_dialog)
			this.make_perm_dialog();
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
					+ '<th>' + __('Read') + '</th>'
					+ '<th>' + __('Write') + '</th>'
					+ '<th>' + __('Create') + '</th>'
					+ '<th>' + __('Delete') + '</th>'
					+ '<th>' + __('Submit') + '</th>'
					+ '<th>' + __('Cancel') + '</th>'
					+ '<th>' + __('Amend') + '</th>'
					+ '<th>' + __('Set User Permissions') + '</th>'
					+ '</tr></thead><tbody></tbody></table>');

				for(var i=0, l=r.message.length; i<l; i++) {
					var perm = r.message[i];

					// if permission -> icon
					for(var key in perm) {
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
						<td>%(read)s</td>\
						<td>%(write)s</td>\
						<td>%(create)s</td>\
						<td>%(delete)s</td>\
						<td>%(submit)s</td>\
						<td>%(cancel)s</td>\
						<td>%(amend)s</td>\
						<td>%(set_user_permissions)s</td>\
						</tr>', perm));
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