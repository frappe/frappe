import DataTable from 'frappe-datatable';

export default function make_datatable(container, doctype) {
	let web_list_start = 0;
	const web_list_page_length = 20;
	let web_list_datatable;

	return new Promise(resolve => {
		frappe.call({
			method: 'frappe.website.doctype.web_form.web_form.get_in_list_view_fields',
			args: { doctype },
			callback: (r) => {
				const docfields = r.message;

				frappe.call({
					method: 'frappe.client.get_list',
					args: { doctype, fields: docfields.map(df => df.fieldname) },
					callback: (r) => {
						const data = r.message || [];

						web_list_datatable = new DataTable(container + ' .results', {
							columns: docfields.map(df => ({ name: df.label, id: df.fieldname })),
							data,
							layout: 'fluid'
						});

						$(container + ' .btn-more').on('click', () => {
							web_list_start += web_list_page_length;
							frappe.call({
								method: 'frappe.client.get_list',
								args: {
									doctype,
									fields: docfields.map(df => df.fieldname),
									limit_start: web_list_start
								},
								callback: (r) => {
									const data = r.message || [];

									web_list_datatable.appendRows(data);
								}
							});
						});

						resolve(web_list_datatable);
					}
				});
			}
		});
	});
}
