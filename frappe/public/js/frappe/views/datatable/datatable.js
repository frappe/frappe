/* eslint-disable */
frappe.provide('frappe.views');

frappe.views.DataTable = class DataTable {
	constructor({ wrapper }) {
		this.wrapper = wrapper;

		const assets = [
			'/assets/frappe/css/datatable.css'
		]
		frappe.require(assets, () => {
			this.prepare();
		});
	}

	prepare() {
		this.prepare_dom();
	}

	prepare_dom() {
		this.wrapper.html(`
			<div class="data-table">
				<div class="data-table-header">
				</div>
				<div class="body-scrollable">
				<div class="data-table-body">
				</div>
				</div>
				<div class="data-table-footer">
				</div>
			</div>
		`);

		this.header = this.wrapper.find('.data-table-header');
		this.body_scrollable = this.wrapper.find('.body-scrollable');
		this.body = this.wrapper.find('.data-table-body');
		this.footer = this.wrapper.find('.data-table-footer');
	}

	render({ columns, rows }) {

		this.header.html(get_header());
		this.body.html(get_body());

		this.body_scrollable.css({
			width: this.header.width(),
			marginTop: this.header.height()
		});

		function get_header() {
			return `
				<div class="data-table-row">
					${columns.map(
						col => get_col(col.fieldname, col.width)
					).join('')}
				</div>
			`
		}

		function get_body() {
			return `
				${rows.map(get_row).join('')}
			`
		}

		function get_row(row) {
			return `
				<div class="data-table-row">
					${row.map((col, i) => {
						const width = columns[i].width;
						return get_col(col, width)
					}).join('')}
				</div>
			`
		}

		function get_col(col, width='') {
			return `
				<div class="data-table-col">
					<div style="width: ${width + 'px' || 'auto'}" class="ellipsis">
						${col}
					</div>
				</div>
			`
		}

	}
}


frappe.views.QueryReport2 = class QueryReport2 {
	constructor({ parent }) {
		this.wrapper = parent.page.main;
		this.prepare_report();
		this.make_datatable();

		this.get_data()
			.then(data => {
				this.datatable.render(data);
			});
	}

	prepare_report() {
		this.report_name = frappe.get_route()[1];
	}

	make_datatable() {
		this.datatable = new frappe.views.DataTable({
			wrapper: this.wrapper
		});
	}

	get_data() {
		return new Promise(res => {
			frappe.call({
				method: "frappe.desk.query_report.run",
				type: "GET",
				args: {
					report_name: this.report_name
				},
				callback: r => {
					const data = r.message;
					const columns = this.parse_columns(data.columns);
					const rows = data.result;
					res({ columns, rows });
				}
			});
		});
	}

	parse_columns(columns) {
		return columns.map(column => {
			const part = column.split(':');

			let fieldname, fieldtype, link_doctype, width;
			fieldname = part[0];

			fieldtype = part[1];
			if(fieldtype.includes('/')) {
				const parts = fieldtype.split('/');
				fieldtype = parts[0];
				link_doctype = parts[1];
			}

			width = part[2];

			return {
				fieldname, fieldtype, link_doctype, width
			}
		});
	}
}