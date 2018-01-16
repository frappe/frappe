frappe.pages['modules_setup'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Show or Hide Desktop Icons'),
		single_column: true
	});

	frappe.modules_setup_page = page;

	page.content = $(frappe.templates.modules_setup).appendTo(page.body);

	page.content.find('select[name="setup_for"]').on('change', function() {
		var val = $(this).val();
		page.content.find('select[name="user"]').toggle(val !== "everyone");
		page.content.find('.block-warning').toggleClass('hidden', val !== 'everyone');
		frappe.reload_modules_setup_icons(page);
	});

	page.content.find('select[name="user"]').on('change', function() {
		frappe.reload_modules_setup_icons(page);
	});

	// return selected user or null (if everyone)
	page.get_user = function() {
		var selected_user = null;
		if(page.content.find('select[name="setup_for"]').length) {
			if(page.content.find('select[name="setup_for"]').val()==="everyone") {
				selected_user = null;
			} else {
				selected_user = page.content.find('select[name="user"]').val();
			}
		} else {
			selected_user = frappe.boot.user.name;
		}
		return selected_user;
	}

	frappe.reload_modules_setup_icons(page);

	// save action
	page.set_primary_action('Save', () => {

		frappe.call({
			method: 'frappe.core.page.modules_setup.modules_setup.update',
			args: {
				hidden_list: page.form.fields_dict.icons.get_unchecked_options(),
				user: page.get_user()
			},
			freeze: true
		});
	});

	// for ctrl+s
	wrapper.save_action = function() {
		page.btn_primary.trigger('click');
	};

	// application installer
	if(frappe.user_roles.includes('System Manager')) {
		page.add_inner_button('Install Apps', function() {
			frappe.set_route('applications');
		});
	}

	// setup select all
	$('.check-all').on('click', function() {
		$(wrapper).find('input.module-select').prop('checked', $(this).prop('checked'));
	});

}

frappe.pages['modules_setup'].on_page_show = function(wrapper) {
	if(frappe.route_options) {
		frappe.modules_setup_page.content.find('select[name="setup_for"]')
			.val('user').trigger('change');
		frappe.modules_setup_page.content.find('select[name="user"]')
			.val(frappe.route_options.user).trigger('change');

		frappe.route_options = null;
	}
}

// reload modules html (with new hidden / blocked settings for given user)
frappe.reload_modules_setup_icons = function(page) {
	console.log(page.get_user());
	frappe.call({
		method: 'frappe.core.page.modules_setup.modules_setup.get_module_icons',
		args: {
			user: page.get_user()
		},
		freeze: true,
		callback: function(r) {
			if(r.message) {
				console.log('message', r.message);
				const icons = r.message.icons;
				const user = r.message.user;
				let $wrapper = page.wrapper.find('.modules-setup-icons');
				$wrapper.empty();
				page.form = new frappe.ui.FieldGroup({
					body: $wrapper.get(0),
					no_submit_on_enter: true,
					fields: [
						{
							label: __('Icons'),
							fieldname: "icons",
							fieldtype: "MultiCheck",
							options: icons.map(icon => {
								const uncheck = user ? icon.hidden : icon.blocked;
								return { label: icon.value, value: icon.value, checked:!uncheck };
							}),
							select_all: 1
						}
					]
				});
				page.form.make();
			}
		}
	});
}
