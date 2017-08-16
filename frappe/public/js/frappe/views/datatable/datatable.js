(function() {

/* eslint-disable */
frappe.provide('frappe.views');

frappe.views.DataTable = class DataTable {
	constructor({ wrapper }) {
		this.wrapper = wrapper;
		this.make_dom();
		this.bind_events();
	}

	make_dom() {
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

		this.header.html(get_header(columns));
		this.body.html(get_body(rows, columns));

		this.body_scrollable.css({
			width: this.header.width(),
			marginTop: this.header.height()
		});
	}

	bind_events() {
		const { body_scrollable } = this;
		body_scrollable.on('click', '.data-table-col', function() {
			body_scrollable.find('.data-table-col').removeClass('selected');
			const $col = $(this);
			$col.addClass('selected');
			// $col.addClass('selected');
		})
		// this.body.scroll(() => console.log('asdf'));
		// this.body_scrollable.scroll(() => {
		// 	var scroll = $(window).scrollTop();
		// 	if (scroll > 0) {
		// 		this.header.addClass("scroll-shadow");
		// 	}
		// 	else {
		// 		this.header.removeClass("scroll-shadow");
		// 	}
		// });
	}
}

function get_header(columns) {
	return `
		<div class="data-table-row">
			${columns.map(
				col => get_col(col.fieldname, col.width)
			).join('')}
		</div>
	`
}

function get_body(rows, columns) {
	return `
		${rows.map(row => get_row(row, columns)).join('')}
	`
}

function get_row(row, columns) {
	return `
		<div class="data-table-row">
			${row.map((col, i) => {
				const width = columns[i].width;
				return get_col(col, width)
			}).join('')}
		</div>
	`
}

function get_col(col, width, is_numeric=false) {
	return `
		<div class="data-table-col ${is_numeric ? 'numeric': ''}">
			<div style="width: ${width ? width + 'px' : 'auto'}" class="ellipsis">
				${col}
			</div>
		</div>
	`
}

})();