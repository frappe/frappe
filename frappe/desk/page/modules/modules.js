frappe.pages['modules'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Modules',
		single_column: false
	});

	frappe.modules_page = page;

	page.wrapper.find('.page-head').toggle(false);
	page.wrapper.find('.page-content').css({'margin-top': '0px'});

	// render sidebar
	page.sidebar.html(frappe.render_template('modules_sidebar', {modules: frappe.get_desktop_icons()}));

	page.wrapper.find('.module-link').on('click', function() {
		render_section($(this).attr('data-name'));
	});

	var render_section = function(module_name) {
		return frappe.call({
			method: "frappe.desk.moduleview.get",
			args: {
				module: module_name
			},
			callback: function(r) {
				m = frappe.get_module(module_name);
				m.data = r.message.data;
				console.log(m);
				page.main.html(frappe.render_template('modules_section', m));
			},
			freeze: true,
		});


	}
}


