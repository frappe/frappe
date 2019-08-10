import DataTable from 'frappe-datatable';

frappe.provide('frappe.data_import');

frappe.data_import.ImportPreview = class ImportPreview {
	constructor(wrapper, csv_array) {
		frappe.import_preview = this;
		this.wrapper = wrapper;
		this.csv_array = csv_array;

		this.prepare_csv_array();
		this.render_datatable();
	}

	prepare_csv_array() {
		this.csv_array = this.csv_array.map(row => {
			return row.map(cell => {
				if (cell == null) {
					return '';
				}
				return cell;
			});
		});
	}

	render_datatable() {
		let columns = this.csv_array[0].map(col => {
			return {
				id: col,
				name: col
			};
		});
		let data = this.csv_array.slice(1);
		this.datatable = new DataTable(this.wrapper.get(0), {
			data,
			columns,
			layout: 'fixed',
			cellHeight: 35,
			headerDropdown: [
				{
					label: __('Change column mapping'),
					action: console.log
				},
				{
					label: __("Don't Import"),
					action: console.log
				}
			]
		});

		this.datatable.style.setStyle(
			'.dt-dropdown__list-item:nth-child(-n+4)',
			{
				display: 'none'
			}
		);
	}
};
