frappe.provide('frappe.model');
frappe.provide('frappe.utils');

/**
 * Opens the Website Meta Tag form if it exists for {route}
 * or creates a new doc and opens the form
 */
frappe.utils.set_meta_tag = function(route) {
	frappe.db.exists('Website Route Meta', route)
		.then(exists => {
			if (exists) {
				frappe.set_route('Form', 'Website Route Meta', route);
			} else {
				// new doc
				const doc = frappe.model.get_new_doc('Website Route Meta');
				doc.__newname = route;
				frappe.set_route('Form', doc.doctype, doc.name);
			}
		});
};
