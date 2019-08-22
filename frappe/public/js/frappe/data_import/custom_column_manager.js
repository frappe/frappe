import ColumnManager from 'frappe-datatable/src/columnmanager';

export default function(header_row) {
	return class CustomColumnManager extends ColumnManager {
		getHeaderHTML(columns) {
			let html = super.getHeaderHTML(columns);

			let header_row_columns = [
				{
					id: '_checkbox',
					colIndex: 0,
					format: () => ''
				}
				// {
				// 	id: 'Sr. No',
				// 	colIndex: 1,
				// 	format: () => ''
				// }
			].concat(
				...header_row.map((col, i) => {
					return {
						id: col,
						name: col,
						align: 'left',
						dropdown: false,
						content: col,
						colIndex: i + 1
					};
				})
			);

			let header_row_html = this.rowmanager.getRowHTML(header_row_columns, {
				rowIndex: 'header-row'
			});
			return header_row_html + html;
		}
	};
}
