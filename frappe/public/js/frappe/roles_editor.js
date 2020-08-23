// TODO: Refactor - use multicheck control
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
			$(me.wrapper).append(repl('<div class="user-role col-md-4" \
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
				me.perm_dialog.set_title(role);
				me.perm_dialog.show();
			}
		});

	},
	make_perm_dialog: function() {
		this.perm_dialog = new frappe.ui.Dialog({
			title: __('Role Permissions')
		});

		this.perm_dialog.$wrapper.find('.modal-dialog').css("width", "800px");
	}
});

frappe.RoleEditor2 = class {
	constructor(wrapper, frm, disable) {
		this.frm = frm;
		this.wrapper = wrapper;
		this.disable = disable;
		let user_roles = this.frm.doc.roles.map(a => a.role);
		this.multicheck = frappe.ui.form.make_control({
			parent: wrapper,
			df: {
				fieldname: "roles",
				fieldtype: "MultiCheck",
				select_all: true,
				columns: 3,
				get_data: () => {
					return frappe.xcall('frappe.core.doctype.user.user.get_all_roles').then(roles => {
						return roles.map(role => {
							return {
								label: __(role),
								value: role,
								checked: user_roles.includes(role)
							};
						});
					});
				},
				on_change: () => {
					this.set_roles_in_table();
					this.frm.dirty();
				}
			},
			render_input: true
		});

		let original_func = this.multicheck.make_checkboxes;
		this.multicheck.make_checkboxes = () => {
			original_func.call(this.multicheck);
			this.multicheck.$wrapper.find('.label-area').click(e => {
				let role = $(e.target).data('unit');
				role && this.show_permissions(role);
				e.preventDefault();
			});
		};
	}
	set_enable_disable() {
		$(this.wrapper).find('input[type="checkbox"]').attr('disabled', this.disable ? true : false);
	}
	show_permissions(role) {
		// show permissions for a role
		if (!this.perm_dialog) {
			this.make_perm_dialog();
		}
		$(this.perm_dialog.body).empty();
		return frappe.xcall('frappe.core.doctype.user.user.get_perm_info', { role })
			.then(permissions => {
				const $body = $(this.perm_dialog.body);
				if (!permissions.length) {
					$body.append(`<div class="text-muted text-center padding">
						${__('{0} role does not have permission on any doctype', [role])}
					</div>`);
				} else {
					$body.append(`
						<table class="user-perm">
							<thead>
								<tr>
									<th> ${__('Document Type')} </th>
									<th> ${__('Level')} </th>
									${frappe.perm.rights.map(p => `<th> ${frappe.unscrub(p)}</th>`).join("")}
								</tr>
							</thead>
							<tbody></tbody>
						</table>
					`);
					permissions.forEach(perm => {
						$body.find('tbody').append(`
							<tr>
								<td>${perm.parent}</td>
								<td>${perm.permlevel}</td>
								${frappe.perm.rights.map(p => `<td>${perm[p] ? '●' : '○'}</td>`).join("")}
							</tr>
						`);
					});
				}
				this.perm_dialog.set_title(role);
				this.perm_dialog.show();
			});
	}
	make_perm_dialog() {
		this.perm_dialog = new frappe.ui.Dialog({
			title: __('Role Permissions')
		});

		this.perm_dialog.$wrapper
			.find('.modal-dialog')
			.css("width", "1200px")
			.css("max-width", "80vw");
	}
	show() {
		let user_roles = this.frm.doc.roles.map(a => a.role);
		this.multicheck.selected_options = user_roles;
		this.multicheck.refresh_input();
		this.set_enable_disable();
	}
	set_roles_in_table() {
		let checked_options = this.multicheck.get_checked_options();
		this.frm.doc.roles.map(role_doc => {
			if (!checked_options.includes(role_doc.role)) {
				frappe.model.clear_doc(role_doc.doctype, role_doc.name);
			}
		});
		checked_options.map(role => {
			if (!this.frm.doc.roles.find(d => d.role === role)) {
				let role_doc = frappe.model.add_child(this.frm.doc, "Has Role", "roles");
				role_doc.role = role;
			}
		});
	}
	get_roles() {
		return {
			checked_roles: this.multicheck.get_checked_options(),
			unchecked_roles: this.multicheck.get_unchecked_options()
		};
	}
};