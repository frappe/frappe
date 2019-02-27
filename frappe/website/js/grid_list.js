export default function make_datatable(container, doctype) {
	let web_list_start = 0;
	const web_list_page_length = 20;
	let web_list_datatable;
	let parent = $(container + ' .results');
	let colnames = [];

	let make_table = function(docfields, data) {
		let table = $(`<table class="table table-bordered table-hover">
			<thead>
				<tr>
					<th><input type="checkbox" class="select-all pull-left"></th>
					<th>Sr</th>
				</tr>
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

		bind_events();
	};


	let truncate = function(txt) {
		if (txt==null) txt = '';
		if (typeof txt==='string' && txt.length > 137) {
			return txt.substr(0, 137) + '...';
		}
		return txt;
	};


	let append_rows = (data) => {
		let body = $(container + ' .results').find('tbody');
		for (let i=0; i<data.length; i++) {
			let tablerow = $(`<tr>
				<td><input type="checkbox"
					class="grid-row-check pull-left"
					data-docname="${data[i].name}"></td>
				<td>${web_list_start + i+1}</td>
			</tr>`).appendTo(body);

			tablerow
				.css({cursor: 'pointer'})
				.click((e) => {
					if ($(e.target).is('[type=checkbox]')) return
					window.location.href = window.location.origin + window.location.pathname + '?name=' + data[i].name;
				});
			for (let fieldname of colnames) {
				let val = data[i][fieldname];
				$(`<td>${truncate(val)}</td>`).appendTo(tablerow);
			}
		}

	};


	const bind_events = () => {
		parent.on('click', 'input[type="checkbox"]:not(.select-all)', (e) => {
			set_actions();
			e.stopPropagation();
		});

		let select_all = (deselect=false) => {
			parent.find(`:checkbox:not(.select-all)`).prop("checked", deselect);
		};
		$('.select-all').on('click', function(e) {
			select_all($(this).prop('checked'));
			set_actions();
			e.stopPropagation();
		});

		$('.btn-delete').on('click', () => {
			let web_form_names_to_delete = [];

			$.each(parent.find('input[type="checkbox"]:checked:not(.select-all)'), (i, node) => {
				web_form_names_to_delete.push($(node).attr('data-docname'));
			});

			if(web_form_names_to_delete.length) {
				frappe.call({
					type:"POST",
					method: "frappe.website.doctype.web_form.web_form.delete_multiple",
					args: {
						"web_form_name": window.web_form_settings.web_form_name,
						"docnames": web_form_names_to_delete
					},
					btn: $('.btn-delete'),
					callback: function(r) {
						if(!r.exc) {
							location.reload();
						}
					}
				});
			}
		});
	};


	const set_actions = () => {
		const show_delete = Boolean(parent.find('input[type="checkbox"]:checked').length);
		$('.page-header-actions-block').toggleClass('actions-mode', show_delete);
	};


	return new Promise(resolve => {
		frappe.call({
			method: 'frappe.website.doctype.web_form.web_form.get_in_list_view_fields',
			args: { doctype },
			callback: (r) => {
				const docfields = r.message;
				var data = frappe.utils.get_query_params();
				data.doctype = doctype;
				data.fields = docfields.map(df => df.fieldname);
				data.web_form_name = window.web_form_settings.web_form_name;
				frappe.call({
					method: 'frappe.www.list.get_list_data',
					args: data,
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
