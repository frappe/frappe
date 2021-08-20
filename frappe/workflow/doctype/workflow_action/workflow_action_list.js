frappe.listview_settings['Workflow Action'] = {
	get_form_link: (doc) => {
		let doctype = '';
		let docname = '';
		if(doc.status === 'Open') {
			doctype = doc.reference_doctype;
			docname = doc.reference_name;
		} else {
			doctype = 'Workflow Action';
			docname = doc.name;
		}
		docname = docname.match(/[%'"]/)
			? encodeURIComponent(docname)
			: docname;

		const link = '/app/' + frappe.router.slug(doctype) + '/' + docname;
		return link;
	}
};