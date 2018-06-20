frappe.provide('frappe.ui.toolbar');

frappe.ui.toolbar.ModulesSelect = class {
	constructor() {
		this.user = frappe.boot.user.name;
		this.setup();
	}

	setup() {
		this.dialog = new frappe.ui.Dialog({
			title: __('Set Desktop Icons'),
			fields: [
				{
					label: __('Setup for'),
					fieldname: 'setup_for',
					fieldtype: 'Select',
					options: [
						{label: __('User'), value: 'user'},
						{label: __('Everyone'), value: 'everyone'}
					],
					default: 'user',
					onchange: () => {
						let field = this.$setup_for;
						if(field.get_value() === 'everyone') {
							this.$user.$wrapper.hide();
							this.user = undefined;
							field.set_description(__('Limit icon choices for all users.'));
						} else {
							this.$user.$wrapper.show();
							this.user = this.$user.get_value();
							field.set_description('');
						}
						this.$icons_list.refresh();
					}
				},
				{ fieldtype: 'Column Break' },
				{
					label: __('User'),
					fieldname: 'user',
					fieldtype: 'Link',
					options: 'User',
					default: frappe.boot.user.name,
					onchange: () => {
						this.user = this.get_value() || frappe.boot.user.name;
						this.$icons_list.refresh();
					}
				},
				{ fieldtype: 'Section Break' },
				{
					// label: __('Icons'),
					fieldname: 'icons',
					fieldtype: 'MultiCheck',
					select_all: 1,
					columns: 2,
					get_data: () => {
						return new Promise((resolve) => {
							frappe.call({
								method: 'frappe.desk.doctype.desktop_icon.desktop_icon.get_module_icons',
								args: {user: this.user},
								freeze: true,
								callback: (r) => {
									const icons = r.message.icons;
									const user = r.message.user;
									resolve(icons
										.map(icon => {
											const uncheck = user ? icon.hidden : icon.blocked;
											return { label: icon.value, value: icon.module_name, checked:!uncheck };
										}).sort(function(a, b){
											if(a.label < b.label) return -1;
											if(a.label > b.label) return 1;
											return 0;
										})
									);
								}
							});
						});
					}
				}
			]
		});

		this.dialog.set_primary_action(__('Save'), () => {
			frappe.call({
				method: 'frappe.desk.doctype.desktop_icon.desktop_icon.update_icons',
				args: {
					hidden_list: this.$icons_list.get_unchecked_options(),
					user: this.user
				},
				freeze: true,
				callback: () => {
					window.location.href = '';
				}
			});
		});

		this.$icons_list = this.dialog.fields_dict.icons;
		this.$setup_for = this.dialog.fields_dict.setup_for;
		this.$user = this.dialog.fields_dict.user;
	}

	show(user) {
		if(user) {
			this.user = user || frappe.boot.user.name;
			this.$icons_list.refresh();
		}
		this.dialog.show();
	}
};