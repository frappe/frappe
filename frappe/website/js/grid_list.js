import DataTable from 'frappe-datatable';

export default function make_datatable(container, doctype) {
	let web_list_start = 0;
	const web_list_page_length = 20;
	let web_list_datatable;
	let parent = $(container + ' .results');
	let colnames = [];

	let make_table = function(docfields, data) {
		let table = $(`<table class="table table-bordered table-hover">
			<thead>
				<tr><th>Sr</th></tr>
			</thead>
			<tbody></tbody>
		</table>`).appendTo(parent);
		let headrow = table.find('thead tr');
		for (let i=0; i<docfields.length; i++) {
			let df = docfields[i];
			$(`<th>${df.label}</th>`).appendTo(headrow);
			colnames.push(df.fieldname);
		}

		append_rows(data);
	};


	let append_rows = (data) => {
		let body = $(container + ' .results').find('tbody');
		for (let i=0; i<data.length; i++) {
			let tablerow = $(`<tr><td>${web_list_start + i+1}</td></tr>`).appendTo(body);
			tablerow
				.css({cursor: 'pointer'})
				.click(() => {
					window.location.href = window.location.href + '?name=' + data[i].name;
				});
			for (let fieldname of colnames) {
				let val = data[i][fieldname];
				if (val==null) val = '';
				$(`<td>${val}</td>`).appendTo(tablerow);
			}
		}

	}

	return new Promise(resolve => {
		frappe.call({
			method: 'frappe.website.doctype.web_form.web_form.get_in_list_view_fields',
			args: { doctype },
			callback: (r) => {
				const docfields = r.message;

				frappe.call({
					method: 'frappe.www.list.get_list_data',
					args: {
						doctype,
						fields: docfields.map(df => df.fieldname),
						web_form_name: window.web_form_settings.web_form_name
					},
					callback: (r) => {
						const data = r.message || [];
						make_table(docfields, data);

						$(container + ' .btn-more').on('click', () => {
							web_list_start += web_list_page_length;
							frappe.call({
								method: 'frappe.www.list.get_list_data',
								args: {
									doctype,
									fields: docfields.map(df => df.fieldname),
									limit_start: web_list_start,
									web_form_name: window.web_form_settings.web_form_name
								},
								callback: (r) => {
									const data = r.message || [];

									append_rows(data);
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
