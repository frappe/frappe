frappe.pages['background_jobs'].on_page_load = function(wrapper) {
	frappe.pages.background_jobs.page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Background Jobs',
		single_column: true
	});
}

frappe.pages['background_jobs'].on_page_show = function(wrapper) {
	frappe.pages.background_jobs.refresh_jobs();
}

frappe.pages.background_jobs.refresh_jobs = function() {
	var page = frappe.pages.background_jobs.page;

	// don't call if already waiting for a response
	if(page.called) return;
	page.called = true;
	frappe.call({
		method: 'frappe.core.page.background_jobs.background_jobs.get_info',
		callback: function(r) {
			page.called = false;
			page.body.find('.list-jobs').remove();
			$(frappe.render_template('background_jobs', {jobs:r.message || []})).appendTo(page.body);

			if(frappe.get_route()[0]==='background_jobs') {
				frappe.background_jobs_timeout = setTimeout(frappe.pages.background_jobs.refresh_jobs, 2000);
			}
		}
	});
}
