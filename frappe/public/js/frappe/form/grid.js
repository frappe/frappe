// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

import GridRow from "./grid_row";
import GridPagination from './grid_pagination';

frappe.ui.form.get_open_grid_form = function() {
	return $(".grid-row-open").data("grid_row");
}

frappe.ui.form.close_grid_form = function() {
	var open_form = frappe.ui.form.get_open_grid_form();
	open_form && open_form.hide_form();

	// hide editable row too
	if(frappe.ui.form.editable_row) {
		frappe.ui.form.editable_row.toggle_editable_row(false);
	}
}


export default class Grid {
	constructor(opts) {
		$.extend(this, opts);
		this.fieldinfo = {};
		this.doctype = this.df.options;

		if(this.doctype) {
			this.meta = frappe.get_meta(this.doctype);
		}
		this.fields_map = {};
		this.template = null;
		this.multiple_set = false;
		if(this.frm && this.frm.meta.__form_grid_templates
			&& this.frm.meta.__form_grid_templates[this.df.fieldname]) {
			this.template = this.frm.meta.__form_grid_templates[this.df.fieldname];
		}

		this.is_grid = true;
	}

	allow_on_grid_editing() {
		if(frappe.utils.is_xs()) {
			return false;
		} else if(this.meta && this.meta.editable_grid || !this.meta) {
			return true;
		} else {
			return false;
		}
	}

	make() {

		let template = `<div class="form-group grid-field">
			<div class="clearfix">
				<label class="control-label" style="padding-right: 0px;">${__(this.df.label || '')}</label>
			</div>
			<div class="grid-custom-buttons">
			</div>
			<div class="form-grid">
				<div class="grid-heading-row"></div>
				<div class="grid-body">
					<div class="rows"></div>
					<div class="grid-empty text-center">${__("No Data")}</div>
				</div>
			</div>
			<div class="small form-clickable-section grid-footer">
				<div class="row">
					<div class="col-sm-5 grid-buttons">
						<button class="btn btn-xs btn-danger grid-remove-rows hidden"
							style="margin-right: 4px;"
							data-action="delete_rows">
							${__("Delete")}
						</button>
						<button class="btn btn-xs btn-danger grid-remove-all-rows hidden"
							style="margin-right: 4px;"
							data-action="delete_all_rows">
							${__("Delete All")}
						</button>
						<button class="grid-add-multiple-rows btn btn-xs btn-default hidden"
							style="margin-right: 4px;">
							${__("Add Multiple")}</a>
						</button>
						<!-- hack to allow firefox include this in tabs -->
						<button class="btn btn-xs btn-default grid-add-row">
							${__("Add Row")}
						</button>
					</div>
					<div class="col-sm-4 grid-pagination">
					</div>
					<div class="col-sm-3 text-right">
						<a href="#" class="grid-download btn btn-xs btn-default hidden"
							style="margin-left: 4px;">
							${__("Download")}</a>
						<a href="#" class="grid-upload btn btn-xs btn-default hidden"
							style="margin-left: 4px;">
							${__("Upload")}</a>
					</div>
				</div>
			</div>
		</div>`;

		this.wrapper = $(template)
			.appendTo(this.parent)
			.attr('data-fieldname', this.df.fieldname);

		frappe.utils.bind_actions_with_object(this.wrapper, this);

		this.form_grid = this.wrapper.find('.form-grid');

		this.setup_add_row();

		this.setup_grid_pagination();

		this.custom_buttons = {};
		this.grid_buttons = this.wrapper.find('.grid-buttons');
		this.grid_custom_buttons = this.wrapper.find('.grid-custom-buttons');
		this.remove_rows_button = this.grid_buttons.find('.grid-remove-rows');
		this.remove_all_rows_button = this.grid_buttons.find('.grid-remove-all-rows');

		this.setup_allow_bulk_edit();
		this.setup_check();
		if(this.df.on_setup) {
			this.df.on_setup(this);
		}
	}

	setup_grid_pagination() {
		this.grid_pagination = new GridPagination({
			grid: this,
			wrapper: this.wrapper,
		});
	}

	setup_check() {

		this.wrapper.on('click', '.grid-row-check', (e) => {
			var $check = $(e.currentTarget);
			if ($check.parents('.grid-heading-row:first').length !== 0) {
				// select all?
				var checked = $check.prop('checked');
				$check.parents('.form-grid:first')
					.find('.grid-row-check').prop('checked', checked);

				// set all
				let result_length = this.grid_pagination.get_result_length();
				let page_index = this.grid_pagination.page_index;
				let page_length = this.grid_pagination.page_length;
				for (var ri = (page_index-1)*page_length; ri < result_length; ri++) {
					this.grid_rows[ri].doc.__checked = checked ? 1: 0;
				}
			} else {
				var docname = $check.parents('.grid-row:first').attr('data-name');
				this.grid_rows_by_docname[docname].select($check.prop('checked'));
			}
			this.refresh_remove_rows_button();
		});

	}

	delete_rows() {
		var dirty = false;

		let tasks = [];
		let selected_children = this.get_selected_children();
		selected_children.forEach(doc => {
			tasks.push(() => {
				if (!this.frm) {
					this.df.data = this.get_data();
					this.df.data = this.df.data.filter(row => row.idx != doc.idx);
				}
				this.grid_rows_by_docname[doc.name].remove();
				dirty = true;
			});
			tasks.push(() => frappe.timeout(0.1));
		});

		if (!this.frm) {
			tasks.push(() => {
				// reorder idx of df.data
				this.df.data.forEach((row, index) => row.idx = index + 1);
			});
		}

		tasks.push(() => {
			if (dirty) this.refresh();
		});

		frappe.run_serially(tasks);

		this.wrapper.find('.grid-heading-row .grid-row-check:checked:first').prop('checked', 0);
		if (selected_children.length == this.grid_pagination.page_length) {
			frappe.utils.scroll_to(this.wrapper);
		}
	}

	delete_all_rows() {
		frappe.confirm(__("Are you sure you want to delete all rows?"), () => {
			this.frm.doc[this.df.fieldname] = [];
			$(this.parent).find('.rows').empty();
			this.grid_rows = [];

			this.wrapper.find('.grid-heading-row .grid-row-check:checked:first').prop('checked', 0);
			this.refresh();
			frappe.utils.scroll_to(this.wrapper);
		});

	}

	select_row(name) {
		this.grid_rows_by_docname[name].select();
	}

	remove_all() {
		this.grid_rows.forEach(row => {
			row.remove();
		});
	}

	refresh_remove_rows_button() {
		this.remove_rows_button.toggleClass('hidden',
			this.wrapper.find('.grid-body .grid-row-check:checked:first').length ? false : true);
		this.remove_all_rows_button.toggleClass('hidden',
			this.wrapper.find('.grid-heading-row .grid-row-check:checked:first').length ? false : true);
	}

	get_selected() {
		return (this.grid_rows || []).map(row => {
			return row.doc.__checked ? row.doc.name : null;
		}).filter(d => {
			return d;
		});
	}

	get_selected_children() {
		return (this.grid_rows || []).map(row => {
			return row.doc.__checked ? row.doc : null;
		}).filter(d => {
			return d;
		});
	}

	make_head() {
		// labels
		if (!this.header_row) {
			this.header_row = new GridRow({
				parent: $(this.parent).find(".grid-heading-row"),
				parent_df: this.df,
				docfields: this.docfields,
				frm: this.frm,
				grid: this
			});
		}
	}

	refresh(force) {
		this.data = this.get_data();

		!this.wrapper && this.make();
		let $rows = $(this.parent).find('.rows');

		this.setup_fields();

		if (this.frm) {
			this.display_status = frappe.perm.get_field_display_status(this.df, this.frm.doc,
				this.perm);
		} else if (this.df.is_web_form && this.control) {
			this.display_status = this.control.get_status();
		} else {
			// not in form
			this.display_status = 'Write';
		}

		if(this.display_status === "None") return;

		// redraw
		this.make_head();

		if (!this.grid_rows) {
			this.grid_rows = [];
		}

		this.truncate_rows();
		this.grid_rows_by_docname = {};

		this.grid_pagination.update_page_numbers();
		this.render_result_rows($rows, false);
		this.grid_pagination.check_page_number();
		this.wrapper.find('.grid-empty').toggleClass('hidden', Boolean(this.data.length));

		// toolbar
		this.setup_toolbar();
		this.toggle_checkboxes(this.display_status !== 'Read');

		// sortable
		if (this.frm && this.is_sortable() && !this.sortable_setup_done) {
			this.make_sortable($rows);
			this.sortable_setup_done = true;
		}

		this.last_display_status = this.display_status;
		this.last_docname = this.frm && this.frm.docname;

		// red if mandatory
		this.form_grid.toggleClass('error', !!(this.df.reqd && !(this.data && this.data.length)));

		this.refresh_remove_rows_button();

		this.wrapper.trigger('change');
	}


	render_result_rows($rows, append_row) {
		let result_length = this.grid_pagination.get_result_length();
		let page_index = this.grid_pagination.page_index;
		let page_length = this.grid_pagination.page_length;
		if (!this.grid_rows) {
			return;
		}
		for (var ri = (page_index-1)*page_length; ri < result_length; ri++) {
			var d = this.data[ri];
			if (!d) {
				return;
			}
			if (d.idx===undefined) {
				d.idx = ri + 1;
			}
			if (this.grid_rows[ri] && !append_row) {
				var grid_row = this.grid_rows[ri];
				grid_row.doc = d;
				grid_row.refresh();
			} else {
				var grid_row = new GridRow({
					parent: $rows,
					parent_df: this.df,
					docfields: this.docfields,
					doc: d,
					frm: this.frm,
					grid: this
				});
				this.grid_rows[ri] = grid_row;
			}

			this.grid_rows_by_docname[d.name] = grid_row;
		}
	}

	setup_toolbar() {

		if (this.is_editable()) {
			this.wrapper.find('.grid-footer').toggle(true);

			// show, hide buttons to add rows
			if (this.cannot_add_rows || (this.df && this.df.cannot_add_rows)) {
				// add 'hidden' to buttons
				this.wrapper.find('.grid-add-row, .grid-add-multiple-rows')
					.addClass('hidden');
			} else {
				// show buttons
				this.wrapper.find('.grid-add-row').removeClass('hidden');

				if (this.multiple_set) {
					this.wrapper.find('.grid-add-multiple-rows').removeClass('hidden');
				}
			}
		} else if (this.grid_rows.length < this.grid_pagination.page_length ) {
			this.wrapper.find('.grid-footer').toggle(false);
		}

	}

	truncate_rows() {
		if (this.grid_rows.length > this.data.length) {
			// remove extra rows
			for (var i = this.data.length; i < this.grid_rows.length; i++) {
				var grid_row = this.grid_rows[i];
				if (grid_row) grid_row.wrapper.remove();
			}
			this.grid_rows.splice(this.data.length);
		}
	}

	setup_fields() {
		// reset docfield
		if (this.frm && this.frm.docname) {
			// use doc specific docfield object
			this.df = frappe.meta.get_docfield(this.frm.doctype, this.df.fieldname,
				this.frm.docname);
		} else {
			// use non-doc specific docfield
			if(this.df.options) {
				this.df = frappe.meta.get_docfield(this.df.options, this.df.fieldname) || this.df || null;
			}
		}

		if (this.doctype && this.frm) {
			this.docfields = frappe.meta.get_docfields(this.doctype, this.frm.docname);
		} else {
			// fields given in docfield
			this.docfields = this.df.fields;
		}

		this.docfields.forEach(df => {
			this.fields_map[df.fieldname] = df;
		});
	}

	refresh_row(docname) {
		this.grid_rows_by_docname[docname] &&
			this.grid_rows_by_docname[docname].refresh();
	}

	make_sortable($rows) {
		new Sortable($rows.get(0), {
			group: {name: this.df.fieldname},
			handle: '.sortable-handle',
			draggable: '.grid-row',
			animation: 100,
			filter: 'li, a',
			onMove: (event) => {
				// don't move if editable
				if (!this.is_editable()) {
					return false;
				}
				// prevent drag behaviour if _sortable property is "false"
				let idx = $(event.dragged).closest('.grid-row').attr('data-idx');
				let doc = this.data[idx%this.grid_pagination.page_length];
				if (doc && doc._sortable === false) {
					return false;
				}
			},
			onUpdate: (event) => {
				let idx = $(event.item).closest('.grid-row').attr('data-idx') - 1;
				let doc = this.data[idx%this.grid_pagination.page_length];
				this.renumber_based_on_dom();
				this.frm.script_manager.trigger(this.df.fieldname + "_move", this.df.options, doc.name);
				this.refresh();
				this.frm.dirty();
			}
		});

		$(this.frm.wrapper).trigger("grid-make-sortable", [this.frm]);
	}

	get_data() {
		var data = this.frm ?
			this.frm.doc[this.df.fieldname] || []
			: this.df.data || this.get_modal_data();
		// data.sort(function(a, b) { return a.idx - b.idx});
		return data;
	}

	get_modal_data() {
		return this.df.get_data ? this.df.get_data().filter(data => {
			if (!this.deleted_docs || !in_list(this.deleted_docs, data.name)) {
				return data;
			}
		}) : [];
	}

	set_column_disp(fieldname, show) {
		if($.isArray(fieldname)) {
			for(var i=0, l=fieldname.length; i<l; i++) {
				var fname = fieldname[i];
				this.get_docfield(fname).hidden = show ? 0 : 1;
				this.set_editable_grid_column_disp(fname, show);
			}
		} else {
			this.get_docfield(fieldname).hidden = show ? 0 : 1;
			this.set_editable_grid_column_disp(fieldname, show);
		}

		this.refresh(true);
	}

	set_editable_grid_column_disp(fieldname, show) {
		//Hide columns for editable grids
		if (this.meta.editable_grid && this.grid_rows) {
			this.grid_rows.forEach( row => {
				row.columns_list.forEach( column => {
					//Hide the column specified
					if (column.df.fieldname == fieldname) {
						if (show) {
							column.df.hidden = false;

							//Show the static area and hide field area if it is not the editable row
							if  (row != frappe.ui.form.editable_row) {
								column.static_area.show();
								column.field_area && column.field_area.toggle(false);
							}
							//Hide the static area and show field area if it is the editable row
							else {
								column.static_area.hide();
								column.field_area && column.field_area.toggle(true);

								//Format the editable column appropriately if it is now visible
								if (column.field) {
									column.field.refresh();
									if (column.field.$input) column.field.$input.toggleClass('input-sm', true);
								}
							}
						}
						else {
							column.df.hidden = true;
							column.static_area.hide();
						}
					}
				});
			});
		}

		this.refresh();
	}

	toggle_reqd(fieldname, reqd) {
		this.get_docfield(fieldname).reqd = reqd;
		this.refresh();
	}

	toggle_enable(fieldname, enable) {
		this.get_docfield(fieldname).read_only = enable ? 0 : 1;
		this.refresh();
	}

	toggle_display(fieldname, show) {
		this.get_docfield(fieldname).hidden = show ? 0 : 1;
		this.refresh();
	}

	toggle_checkboxes(enable) {
		this.wrapper.find(".grid-row-check").prop('disabled', !enable)
	}

	get_docfield(fieldname) {
		return frappe.meta.get_docfield(this.doctype, fieldname, this.frm ? this.frm.docname : null);
	}

	get_row(key) {
		if (typeof key == 'number') {
			if (key < 0) {
				return this.grid_rows[this.grid_rows.length + key];
			} else {
				return this.grid_rows[key];
			}
		} else {
			return this.grid_rows_by_docname[key];
		}
	}

	get_grid_row(key) {
		return this.get_row(key);
	}

	get_field(fieldname) {
		// Note: workaround for get_query
		if(!this.fieldinfo[fieldname])
			this.fieldinfo[fieldname] = {
			}
		return this.fieldinfo[fieldname];
	}

	set_value(fieldname, value, doc) {
		if(this.display_status!=="None" && this.grid_rows_by_docname[doc.name]) {
			this.grid_rows_by_docname[doc.name].refresh_field(fieldname, value);
		}
	}

	setup_add_row() {
		this.wrapper.find(".grid-add-row").click(() => {
			this.add_new_row(null, null, true, null, true);
			this.set_focus_on_row();

			return false;
		});
	}

	add_new_row(idx, callback, show, copy_doc, go_to_last_page=false) {
		if (this.is_editable()) {
			if (go_to_last_page) {
				this.grid_pagination.go_to_last_page_to_add_row();
			}
			if (this.frm) {
				var d = frappe.model.add_child(this.frm.doc, this.df.options, this.df.fieldname, idx);
				if (copy_doc) {
					d = this.duplicate_row(d, copy_doc);
				}
				d.__unedited = true;
				this.frm.script_manager.trigger(this.df.fieldname + "_add", d.doctype, d.name);
				this.refresh();
			} else {
				if (!this.df.data) {
					this.df.data = this.get_data() || [];
				}
				this.df.data.push({idx: this.df.data.length+1, __islocal: true});
				this.refresh();
			}

			if (show) {
				if (idx) {
					// always open inserted rows
					this.wrapper.find("[data-idx='"+idx+"']").data("grid_row")
						.toggle_view(true, callback);
				} else {
					if (!this.allow_on_grid_editing()) {
						// open last row only if on-grid-editing is disabled
						this.wrapper.find(".grid-row:last").data("grid_row")
							.toggle_view(true, callback);
					}
				}
			}

			return d;
		}
	}

	renumber_based_on_dom() {
		// renumber based on dom
		let $rows = $(this.parent).find(".rows");

		$rows.find(".grid-row").each( (i, item) => {
			let $item = $(item);
			let index = (this.grid_pagination.page_index-1)*this.grid_pagination.page_length+i;
			let d = locals[this.doctype][$item.attr('data-name')];
			d.idx = index + 1;
			$item.attr('data-idx', d.idx);

			this.frm.doc[this.df.fieldname][index] = (d);
			this.data[index] = d;
			this.grid_rows[index]=(this.grid_rows_by_docname[d.name]);
		});
	}

	duplicate_row(d, copy_doc) {
		$.each(copy_doc, function(key, value) {
			if(!["creation", "modified", "modified_by", "idx", "owner",
				"parent", "doctype", "name", "parentield"].includes(key)) {
				d[key] = value;
			}
		});

		return d;
	}

	set_focus_on_row(idx) {
		if(!idx) {
			idx = this.grid_rows.length - 1;
		}
		setTimeout(() => {
			this.grid_rows[idx].row
				.find('input[type="Text"],textarea,select').filter(':visible:first').focus();
		}, 100);
	}

	setup_visible_columns() {
		if (this.visible_columns) return;

		var total_colsize = 1,
			fields = this.editable_fields || this.docfields;

		this.visible_columns = [];

		for (var ci in fields) {
			var _df = fields[ci];

			// get docfield if from fieldname
			df = this.fields_map[_df.fieldname];

			if (!df.hidden
				&& (this.editable_fields || df.in_list_view)
				&& (this.frm && this.frm.get_perm(df.permlevel, "read") || !this.frm)
				&& !in_list(frappe.model.layout_fields, df.fieldtype)) {

				if (df.columns) {
					df.colsize=df.columns;
				} else {
					var colsize = 2;
					switch (df.fieldtype) {
						case "Text": break;
						case "Small Text": colsize = 3; break;
						case "Check": colsize = 1;
					}
					df.colsize = colsize;
				}

				// attach formatter on refresh
				if (df.fieldtype == 'Link' && !df.formatter && df.parent && frappe.meta.docfield_map[df.parent]) {
					const docfield = frappe.meta.docfield_map[df.parent][df.fieldname];
					if (docfield && docfield.formatter) {
						df.formatter = docfield.formatter;
					}
				}

				total_colsize += df.colsize;
				if (total_colsize > 11)
					return false;
				this.visible_columns.push([df, df.colsize]);
			}
		}

		// redistribute if total-col size is less than 12
		var passes = 0;
		while (total_colsize < 11 && passes < 12) {
			for (var i in this.visible_columns) {
				var df = this.visible_columns[i][0];
				var colsize = this.visible_columns[i][1];
				if (colsize > 1 && colsize < 11
					&& !in_list(frappe.model.std_fields_list, df.fieldname)) {

					if (passes < 3 && ["Int", "Currency", "Float", "Check", "Percent"].indexOf(df.fieldtype)!==-1) {
						// don't increase col size of these fields in first 3 passes
						continue;
					}

					this.visible_columns[i][1] += 1;
					total_colsize++;
				}

				if (total_colsize > 10)
					break;
			}
			passes++;
		}
	}


	is_editable() {
		return this.display_status=="Write" && !this.static_rows;
	}

	is_sortable() {
		return this.sortable_status || this.is_editable();
	}

	only_sortable(status) {
		if (status===undefined ? true : status) {
			this.sortable_status = true;
			this.static_rows = true;
		}
	}

	set_multiple_add(link, qty) {
		if (this.multiple_set) return;

		var link_field = frappe.meta.get_docfield(this.df.options, link);
		var btn = $(this.wrapper).find(".grid-add-multiple-rows");

		// show button
		btn.removeClass('hidden');

		// open link selector on click
		btn.on("click", () => {
			new frappe.ui.form.LinkSelector({
				doctype: link_field.options,
				fieldname: link,
				qty_fieldname: qty,
				target: this,
				txt: ""
			});
			this.grid_pagination.go_to_last_page_to_add_row();
			return false;
		});
		this.multiple_set = true;
	}

	setup_allow_bulk_edit() {
		let me = this;
		if (this.frm && this.frm.get_docfield(this.df.fieldname).allow_bulk_edit) {
			// download
			this.setup_download();

			const value_formatter_map = {
				"Date": val => val ? frappe.datetime.user_to_str(val) : val,
				"Int": val => cint(val),
				"Check": val => cint(val),
				"Float": val => flt(val),
			};

			// upload
			frappe.flags.no_socketio = true;
			$(this.wrapper).find(".grid-upload").removeClass('hidden').on("click", () => {
				new frappe.ui.FileUploader({
					as_dataurl: true,
					allow_multiple: false,
					on_success(file) {
						var data = frappe.utils.csv_to_array(frappe.utils.get_decoded_string(file.dataurl));
						// row #2 contains fieldnames;
						var fieldnames = data[2];
						me.frm.clear_table(me.df.fieldname);
						$.each(data, (i, row) => {
							if (i > 6) {
								var blank_row = true;
								$.each(row, function(ci, value) {
									if (value) {
										blank_row = false;
										return false;
									}
								});

								if (!blank_row) {
									var d = me.frm.add_child(me.df.fieldname);
									$.each(row, (ci, value) => {
										var fieldname = fieldnames[ci];
										var df = frappe.meta.get_docfield(me.df.options, fieldname);

										d[fieldnames[ci]] = value_formatter_map[df.fieldtype]
											? value_formatter_map[df.fieldtype](value)
											: value;
									});
								}
							}
						});

						me.frm.refresh_field(me.df.fieldname);
						frappe.msgprint({message: __('Table updated'), title: __('Success'), indicator: 'green'});
					}
				});
				return false;
			});
		}
	}

	setup_download() {
		let title = this.df.label || frappe.model.unscrub(this.df.fieldname);
		$(this.wrapper).find(".grid-download").removeClass('hidden').on("click", () => {
			var data = [];
			var docfields = [];
			data.push([__("Bulk Edit {0}", [title])]);
			data.push([]);
			data.push([]);
			data.push([]);
			data.push([__("The CSV format is case sensitive")]);
			data.push([__("Do not edit headers which are preset in the template")]);
			data.push(["------"]);
			$.each(frappe.get_meta(this.df.options).fields, (i, df) => {
				// don't include the read-only field in the template
				if (frappe.model.is_value_type(df.fieldtype)) {
					data[1].push(df.label);
					data[2].push(df.fieldname);
					let description = (df.description || "") + ' ';
					if (df.fieldtype === "Date") {
						description += frappe.boot.sysdefaults.date_format;
					}
					data[3].push(description);
					docfields.push(df);
				}
			});

			// add data
			$.each(this.frm.doc[this.df.fieldname] || [], (i, d) => {
				var row = [];
				$.each(data[2], (i, fieldname) => {
					var value = d[fieldname];

					// format date
					if (docfields[i].fieldtype==="Date" && value) {
						value = frappe.datetime.str_to_user(value);
					}

					row.push(value || "");
				});
				data.push(row);
			});

			frappe.tools.downloadify(data, null, title);
			return false;
		});
	}

	add_custom_button(label, click, position='bottom') {
		// add / unhide a custom button
		const $wrapper = position === 'top' ? this.grid_custom_buttons : this.grid_buttons;
		let $btn = this.custom_buttons[label];
		if (!$btn) {
			$btn = $(`<button class="btn btn-default btn-xs btn-custom">${__(label)}</button>`)
				.prependTo($wrapper)
				.on('click', click);
			this.custom_buttons[label] = $btn;
		} else {
			$btn.removeClass('hidden');
		}
		return $btn;
	}

	clear_custom_buttons() {
		// hide all custom buttons
		this.grid_buttons.find('.btn-custom').addClass('hidden');
	}
}
