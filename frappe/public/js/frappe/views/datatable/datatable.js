(function() {

/* eslint-disable */

class DataTable {
	constructor({ wrapper, events }) {
		this.wrapper = wrapper;
		this.events = events || {};
		this.make_dom();
		this.bind_events();
	}

	make_dom() {
		this.wrapper.html(`
			<div class="data-table">
				<table class="data-table-header table table-bordered">
				</table>
				<div class="body-scrollable">
					<table class="data-table-body table table-bordered">
					</table>
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
		debugger;
		console.log(columns, rows);
		this.columns = this.prepare_columns(columns);
		this.rows = this.prepare_rows(rows);

		this.header.html(get_header(this.columns));
		this.body.html(get_body(this.rows));

		this.set_dimensions();
	}

	refresh_rows(rows) {
		if(rows) {
			this.rows = this.prepare_rows(rows);
		}
		this.body.html(get_body(this.rows));
		this.set_dimensions();
	}

	prepare_columns(columns) {
		return columns.map((col, i) => {
			col.col_index = i;
			col.is_header = 1;
			col.format = val => `<span>${val}</span>`;
			return col;
		});
	}

	prepare_rows(rows) {
		return rows.map((cells, i) => {
			return cells.map((cell, j) => {
				cell.col_index = j;
				cell.row_index = i;
				return cell;
			});
		});
	}

	bind_events() {
		const { body_scrollable, events } = this;
		body_scrollable.on('click', '.data-table-col', function() {
			body_scrollable.find('.data-table-col').removeClass('selected');
			const $col = $(this);
			$col.addClass('selected');
		});

		this.bind_cell_double_click();
		this.bind_resize_column();
		this.bind_sort_column();
	}

	set_dimensions() {
		const me = this;
		// set the width for each cell
		this.header.find('.data-table-col').each(function() {
			const col = $(this);
			const width = col.find('.content').width();
			const col_index = col.attr('data-col-index');
			const selector = `.data-table-col[data-col-index="${col_index}"] .content`;
			const $cell = me.body_scrollable.find(selector);
			$cell.width(width);
		});

		// setting width as 0 will ensure that the
		// header doesn't take the available space
		this.header.css('width', 0);

		this.body_scrollable.css({
			width: this.header.css('width'),
			marginTop: this.header.height()
		});
	}

	bind_cell_double_click() {
		this.body_scrollable.on('dblclick', '.data-table-col', function() {
			const $cell = $(this);
			const row_index = $cell.attr('data-row-index');
			const col_index = $cell.attr('data-col-index');

			events.on_cell_doubleclick.apply(null, [$cell.get(0), row_index, col_index]);
		});
	}

	bind_resize_column() {
		const me = this;
		let is_dragging = false;
		let $curr_cell, start_width, start_x, last_width;

		this.header.on('mousedown', '.data-table-col', function(e) {
			$curr_cell = $(this);
			const col = me.get_column($curr_cell.attr('data-col-index'));
			if(col && col.resizable === false) {
				return;
			}

			is_dragging = true;
			start_width = $curr_cell.find('.content').width();
			start_x = e.pageX;
		});

		$('body').on('mouseup', function(e) {
			if(!$curr_cell) return;

			is_dragging = false;
			const col_index = $curr_cell.attr('data-col-index');
			if($curr_cell) {
				const width = $curr_cell.find('.content').css('width');
				me.set_column_width(col_index, width);
				me.body_scrollable.css('width', me.header.css('width'));
				$curr_cell = null;
			}
		});

		this.header.on('mousemove', '.data-table-col', function(e) {
			if (!is_dragging) return;
			const fwidth = start_width + (e.pageX - start_x);
			$curr_cell.find('.content').width(fwidth);
		});
	}

	bind_sort_column() {
		const me = this;
		this.header.on('click', '.data-table-col .content span', function() {
			const $cell = $(this).closest('.data-table-col');
			const sort_by = $cell.attr('data-sort-by');
			const col_index = $cell.attr('data-col-index');

			if (sort_by === 'none') {
				$cell.attr('data-sort-by', 'asc');
				$cell.find('.content').append('<span class="pull-right octicon octicon-chevron-up">');
			}
			else if (sort_by === 'asc') {
				$cell.attr('data-sort-by', 'desc');
				$cell.find('.content .octicon')
					.removeClass('octicon-chevron-up')
					.addClass('octicon-chevron-down');
			}
			else if (sort_by === 'desc') {
				$cell.attr('data-sort-by', 'none');
				$cell.find('.content .octicon').remove();
			}

			const sort_by_action = $cell.attr('data-sort-by');
			if (me.events.on_sort) {
				me.events.on_sort.apply(null, [col_index, sort_by_action]);
			} else {
				me.sort_rows(col_index, sort_by_action);
				me.refresh_rows();
			}
		});
	}

	sort_rows(col_index, sort_by='none') {
		this.rows.sort((a, b) => {
			const _a_index = a[0].row_index;
			const _b_index = b[0].row_index;
			const _a = a[col_index].data;
			const _b = b[col_index].data;

			if(sort_by === 'none') {
				return _a_index - _b_index;
			}
			else if(sort_by === 'asc') {
				if (_a < _b) return -1;
				if (_a > _b) return 1;
				if (_a === _b) return 0;
			}
			else if(sort_by === 'desc') {
				if (_a < _b) return 1;
				if (_a > _b) return -1;
				if (_a === _b) return 0;
			}
		});
	}

	set_column_width(col_index, width, header=false) {
		const selector = `.data-table-col[data-col-index="${col_index}"] .content`;
		let $el;
		if (header) {
			$el = this.header.find(selector);
		} else {
			$el = this.body_scrollable.find(selector);
		}
		$el.css('width', width);
	}

	get_column(col_index) {
		return this.columns.find(col => col.col_index == col_index);
	}
}

function get_header(columns) {
	const $header = $(`<thead>
		${get_row({cells: columns, is_header: 1})}
	</thead>
	`);

	columns.map(col => {
		if(!col.width) return;
		const $cell_content = $header.find(`.data-table-col[data-col-index="${col.col_index}"] .content`);
		$cell_content.width(col.width);
		// $cell_content.css('max-width', col.width + 'px');
	});

	return $header;
}

function get_body(rows) {
	return `<tbody>
		${rows.html(row => get_row({ cells: row }))}
	</tbody>
	`
}

function get_row(row) {
	const header = row.is_header ? 'data-header' : '';
	const cells = row.cells;
	const data_row_index = !isNaN(cells[0].row_index) ? `data-row-index="${cells[0].row_index}"` : '';

	return `
		<tr class="data-table-row" ${data_row_index} ${header}>
			${cells.html(get_cell)}
		</tr>
	`
}

function get_cell(cell) {
	const custom_attr = [
		!isNaN(cell.col_index) ? `data-col-index="${cell.col_index}"` : '',
		!isNaN(cell.row_index) ? `data-row-index="${cell.row_index}"` : '',
		cell.is_header ? `data-sort-by='none'` : '',
	].join(" ");

	return `
		<td class="data-table-col" ${custom_attr}>
			<div class="content ellipsis">
				${cell.format ? cell.format(cell.data) : cell.data}
			</div>
		</td>
	`
}

Array.prototype.html = function(fn) {
	return this.map(a => fn(a)).join("");
}

window.DataTable = DataTable;

})();