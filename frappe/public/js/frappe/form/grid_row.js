import GridRowForm from './grid_row_form';

export default class GridRow {
	constructor(opts) {
		this.on_grid_fields_dict = {};
		this.on_grid_fields = [];
		$.extend(this, opts);
		if (this.doc && this.parent_df.options) {
			frappe.meta.make_docfield_copy_for(this.parent_df.options, this.doc.name, this.docfields);
			const docfields = frappe.meta.get_docfields(this.parent_df.options, this.doc.name);
			this.docfields = docfields.length ? docfields : opts.docfields;
		}
		this.columns = {};
		this.columns_list = [];
		this.row_check_html = '<input type="checkbox" class="grid-row-check pull-left">';
		this.make();
	}
	make() {
		var me = this;

		this.wrapper = $('<div class="grid-row"></div>').appendTo(this.parent).data("grid_row", this);
		this.row = $('<div class="data-row row"></div>').appendTo(this.wrapper)
			.on("click", function(e) {
				if($(e.target).hasClass('grid-row-check') || $(e.target).hasClass('row-index') || $(e.target).parent().hasClass('row-index')) {
					return;
				}
				if(me.grid.allow_on_grid_editing() && me.grid.is_editable()) {
					// pass
				} else {
					me.toggle_view();
					return false;
				}
			});

		if(this.grid.template && !this.grid.meta.editable_grid) {
			this.render_template();
		} else {
			this.render_row();
		}
		if(this.doc) {
			this.set_data();
		}
	}
	set_data() {
		this.wrapper.data({
			"doc": this.doc
		})
	}
	set_row_index() {
		if(this.doc) {
			this.wrapper
				.attr('data-name', this.doc.name)
				.attr("data-idx", this.doc.idx)
				.find(".row-index span, .grid-form-row-index").html(this.doc.idx)

		}
	}
	select(checked) {
		this.doc.__checked = checked ? 1 : 0;
	}
	refresh_check() {
		this.wrapper.find('.grid-row-check').prop('checked', this.doc ? !!this.doc.__checked : false);
		this.grid.refresh_remove_rows_button();
	}
	remove() {
		var me = this;
		if(this.grid.is_editable()) {
			if(this.frm) {
				if(this.get_open_form()) {
					this.hide_form();
				}

				frappe.run_serially([
					() => {
						return this.frm.script_manager.trigger("before_" + this.grid.df.fieldname + "_remove",
							this.doc.doctype, this.doc.name);
					},
					() => {
						frappe.model.clear_doc(this.doc.doctype, this.doc.name);

						this.frm.script_manager.trigger(this.grid.df.fieldname + "_remove",
							this.doc.doctype, this.doc.name);
						this.frm.dirty();
						this.grid.refresh();
					},
				]).catch((e) => {
					// aborted
					console.trace(e); // eslint-disable-line
				});
			} else {
				let data = null;
				if (this.grid.df.get_data) {
					data = this.grid.df.get_data();
				} else {
					data = this.grid.df.data;
				}

				const index = data.findIndex(d => d.name === me.doc.name);

				if (index > -1) {
					// mutate array directly,
					// else the object reference will be lost
					data.splice(index, 1);
				}
				// remap idxs
				data.forEach(function(d, i) {
					d.idx = i+1;
				});

				this.grid.refresh();
			}
		}
	}
	insert(show, below, duplicate) {
		var idx = this.doc.idx;
		var copy_doc = duplicate ? this.doc : null;
		if(below) idx ++;
		this.toggle_view(false);
		this.grid.add_new_row(idx, null, show, copy_doc);
	}
	move() {
		// promopt the user where they want to move this row
		var me = this;
		frappe.prompt({
			fieldname: 'move_to',
			label: __('Move to Row Number'),
			fieldtype: 'Int',
			reqd: 1,
			default: this.doc.idx,
		}, function(values) {
			if (me.doc._sortable === false) {
				frappe.msgprint(__('Cannot move row'));
				return;
			}

			// renumber and refresh
			let data = me.grid.get_data();
			data.move(me.doc.idx - 1, values.move_to - 1);

			// renum idx
			for(let i=0; i<data.length;i++) {
				data[i].idx = i+1;
			}

			me.toggle_view(false);
			me.grid.refresh();
			$(me.frm.wrapper).trigger("grid-move-row", [me.frm, me]);
		}, __('Move To'), 'Update');
	}
	refresh() {
		if(this.frm && this.doc) {
			this.doc = locals[this.doc.doctype][this.doc.name];
		}

		if(this.grid.template && !this.grid.meta.editable_grid) {
			this.render_template();
		} else {
			this.render_row(true);
		}

		// refresh form fields
		if(this.grid_form) {
			this.grid_form.layout && this.grid_form.layout.refresh(this.doc);
		}
	}
	render_template() {
		this.set_row_index();

		if(this.row_display) {
			this.row_display.remove();
		}

		// row index
		if(this.doc) {
			if(!this.row_index) {
				this.row_index = $('<div style="float: left; margin-left: 15px; margin-top: 8px; \
					margin-right: -20px;">'+this.row_check_html+' <span></span></div>').appendTo(this.row);
			}
			this.row_index.find('span').html(this.doc.idx);
		}

		this.row_display = $('<div class="row-data sortable-handle template-row">'+
			+'</div>').appendTo(this.row)
			.html(frappe.render(this.grid.template, {
				doc: this.doc ? frappe.get_format_helper(this.doc) : null,
				frm: this.frm,
				row: this
			}));
	}
	render_row(refresh) {
		var me = this;
		this.set_row_index();

		// index (1, 2, 3 etc)
		if(!this.row_index) {
			// REDESIGN-TODO: Make translation contextual, this No is Number
			var txt = (this.doc ? this.doc.idx : __("No."));
			this.row_index = $(
				`<div class="row-index sortable-handle col col-xs-1">
					${this.row_check_html}
				<span class="hidden-xs">${txt}</span></div>`)
				.appendTo(this.row)
				.on('click', function(e) {
					if(!$(e.target).hasClass('grid-row-check')) {
						me.toggle_view();
					}
				});
		} else {
			this.row_index.find('span').html(txt);
		}

		this.setup_columns();
		this.add_open_form_button();
		this.refresh_check();

		if(this.frm && this.doc) {
			$(this.frm.wrapper).trigger("grid-row-render", [this]);
		}
	}

	make_editable() {
		this.row.toggleClass('editable-row', this.grid.is_editable());
	}

	is_too_small() {
		return this.row.width() ? this.row.width() < 300 : false;
	}

	add_open_form_button() {
		var me = this;
		if(this.doc && !this.grid.df.in_place_edit) {
			// remove row
			if(!this.open_form_button) {
				this.open_form_button = $(`
					<div class="btn-open-row">
						<a>${frappe.utils.icon('edit', 'xs')}</a>
						<div class="hidden-xs edit-grid-row">${ __("Edit") }</div>
					</div>
				`)
					.appendTo($('<div class="col col-xs-1"></div>').appendTo(this.row))
					.on('click', function() {
						me.toggle_view(); return false;
					});

				if(this.is_too_small()) {
					// narrow
					this.open_form_button.css({'margin-right': '-2px'});
				}
			}
		}
	}

	setup_columns() {
		this.focus_set = false;
		this.grid.setup_visible_columns();

		this.grid.visible_columns.forEach((col, ci) => {
			// to get update df for the row
			let df = this.docfields.find(field => field.fieldname === col[0].fieldname);

			let colsize = col[1];
			let txt = this.doc ?
				frappe.format(this.doc[df.fieldname], df, null, this.doc) :
				__(df.label);

			if (this.doc && df.fieldtype === "Select") {
				txt = __(txt);
			}
			let column;
			if (!this.columns[df.fieldname]) {
				column = this.make_column(df, colsize, txt, ci);
			} else {
				column = this.columns[df.fieldname];
				this.refresh_field(df.fieldname, txt);
			}

			// background color for cell
			if (this.doc) {
				if (df.reqd && !txt) {
					column.addClass('error');
				}
				if (column.is_invalid) {
					column.addClass('invalid');
				} else if (df.reqd || df.bold) {
					column.addClass('bold');
				}
			}
		});
	}

	make_column(df, colsize, txt, ci) {
		let me = this;
		var add_class = ((["Text", "Small Text"].indexOf(df.fieldtype)!==-1) ?
			" grid-overflow-no-ellipsis" : "");
		add_class += (["Int", "Currency", "Float", "Percent"].indexOf(df.fieldtype)!==-1) ?
			" text-right": "";
		add_class += (["Check"].indexOf(df.fieldtype)!==-1) ?
			" text-center": "";

		var $col = $('<div class="col grid-static-col col-xs-'+colsize+' '+add_class+'"></div>')
			.attr("data-fieldname", df.fieldname)
			.attr("data-fieldtype", df.fieldtype)
			.data("df", df)
			.appendTo(this.row)
			.on('click', function() {
				if(frappe.ui.form.editable_row===me) {
					return;
				}
				var out = me.toggle_editable_row();
				var col = this;
				setTimeout(function() {
					$(col).find('input[type="Text"]:first').focus();
				}, 500);
				return out;
			});

		$col.field_area = $('<div class="field-area"></div>').appendTo($col).toggle(false);
		$col.static_area = $('<div class="static-area ellipsis"></div>').appendTo($col).html(txt);

		// set title attribute to see full label for columns in the heading row
		if (!this.doc) {
			$col.attr("title", txt);
		}

		$col.df = df;
		$col.column_index = ci;

		this.columns[df.fieldname] = $col;
		this.columns_list.push($col);

		return $col;
	}

	activate() {
		this.toggle_editable_row(true);
		return this;
	}

	toggle_editable_row(show) {
		var me = this;
		// show static for field based on
		// whether grid is editable
		if(this.grid.allow_on_grid_editing() && this.grid.is_editable() && this.doc && show !== false) {

			// disable other editable row
			if(frappe.ui.form.editable_row
				&& frappe.ui.form.editable_row !== this) {
				frappe.ui.form.editable_row.toggle_editable_row(false);
			}

			this.row.toggleClass('editable-row', true);

			// setup controls
			this.columns_list.forEach(function(column) {
				me.make_control(column);
				column.static_area.toggle(false);
				column.field_area.toggle(true);
			});

			frappe.ui.form.editable_row = this;
			return false;
		} else {
			this.row.toggleClass('editable-row', false);

			this.columns_list.forEach((column, index) => {

				if(!this.frm) {
					let df = this.grid.visible_columns[index][0]

					let txt = this.doc ?
						frappe.format(this.doc[df.fieldname], df, null, this.doc) :
						__(df.label);

					this.refresh_field(df.fieldname, txt)
				}

				if (!column.df.hidden) {
					column.static_area.toggle(true);
				}

				column.field_area && column.field_area.toggle(false);
			});
			frappe.ui.form.editable_row = null;
		}
	}

	make_control(column) {
		if(column.field) return;

		var me = this,
			parent = column.field_area,
			df = column.df;

		// no text editor in grid
		if (df.fieldtype=='Text Editor') {
			df = Object.assign({}, df);
			df.fieldtype = 'Text';
		}

		var field = frappe.ui.form.make_control({
			df: df,
			parent: parent,
			only_input: true,
			with_link_btn: true,
			doc: this.doc,
			doctype: this.doc.doctype,
			docname: this.doc.name,
			frm: this.grid.frm,
			grid: this.grid,
			grid_row: this,
			value: this.doc[df.fieldname]
		});

		// sync get_query
		field.get_query = this.grid.get_field(df.fieldname).get_query;

		if (!field.df.onchange_modified) {
			var field_on_change_function = field.df.onchange;
			field.df.onchange = (e) => {
				field_on_change_function && field_on_change_function(e);
				this.refresh_field(field.df.fieldname);
			};

			field.df.onchange_modified = true;
		}

		field.refresh();
		if(field.$input) {
			field.$input
				.addClass('input-sm')
				.attr('data-col-idx', column.column_index)
				.attr('placeholder', __(df.placeholder || df.label));
			// flag list input
			if (this.columns_list && this.columns_list.slice(-1)[0]===column) {
				field.$input.attr('data-last-input', 1);
			}
		}

		this.set_arrow_keys(field);
		column.field = field;
		this.on_grid_fields_dict[df.fieldname] = field;
		this.on_grid_fields.push(field);

	}

	set_arrow_keys(field) {
		var me = this;
		if (field.$input) {
			field.$input.on('keydown', function(e) {
				var { TAB, UP: UP_ARROW, DOWN: DOWN_ARROW } = frappe.ui.keyCode;
				if (!in_list([TAB, UP_ARROW, DOWN_ARROW], e.which)) {
					return;
				}

				var values = me.grid.get_data();
				var fieldname = $(this).attr('data-fieldname');
				var fieldtype = $(this).attr('data-fieldtype');

				var move_up_down = function(base) {
					if (in_list(['Text', 'Small Text', 'Code', 'Text Editor', 'HTML Editor'], fieldtype) && !e.altKey) {
						return false;
					}
					if (field.autocomplete_open) {
						return false;
					}

					base.toggle_editable_row();
					var input = base.columns[fieldname].field.$input;
					if (input) {
						input.focus();
					}
					return true;
				};

				// TAB
				if (e.which === TAB && !e.shiftKey) {
					var last_column = me.wrapper.find(':input:enabled:last').get(0);
					var is_last_column = $(this).attr('data-last-input') || last_column === this;

					if (is_last_column) {
						// last row
						if (me.doc.idx === values.length) {
							setTimeout(function () {
								me.grid.add_new_row(null, null, true);
								me.grid.grid_rows[me.grid.grid_rows.length - 1].toggle_editable_row();
								me.grid.set_focus_on_row();
							}, 100);
						} else {
							// last column before last row
							me.grid.grid_rows[me.doc.idx].toggle_editable_row();
							me.grid.set_focus_on_row(me.doc.idx);
							return false;
						}
					}
				} else if (e.which === UP_ARROW) {
					if (me.doc.idx > 1) {
						var prev = me.grid.grid_rows[me.doc.idx-2];
						if (move_up_down(prev)) {
							return false;
						}
					}
				} else if (e.which === DOWN_ARROW) {
					if (me.doc.idx < values.length) {
						var next = me.grid.grid_rows[me.doc.idx];
						if (move_up_down(next)) {
							return false;
						}
					}
				}

			});
		}
	}

	get_open_form() {
		return frappe.ui.form.get_open_grid_form();
	}

	toggle_view(show, callback) {
		if(!this.doc) {
			return this;
		}

		if(this.frm) {
			// reload doc
			this.doc = locals[this.doc.doctype][this.doc.name];
		}

		// hide other
		var open_row = this.get_open_form();

		if (show === undefined) show = !open_row;

		// call blur
		document.activeElement && document.activeElement.blur();

		if(show && open_row) {
			if(open_row==this) {
				// already open, do nothing
				callback && callback();
				return;
			} else {
				// close other views
				open_row.toggle_view(false);
			}
		}

		if(show) {
			this.show_form();
		} else {
			this.hide_form();
		}
		callback && callback();

		return this;
	}
	show_form() {
		if (!this.grid_form) {
			this.grid_form = new GridRowForm({
				row: this
			});
		}
		this.grid_form.render();
		this.row.toggle(false);
		// this.form_panel.toggle(true);

		let cannot_add_rows = this.grid.cannot_add_rows || (this.grid.df && this.grid.df.cannot_add_rows);
		this.wrapper
			.find('.grid-insert-row-below, .grid-insert-row, .grid-duplicate-row, .grid-append-row')
			.toggle(!cannot_add_rows);

		this.wrapper.find('.grid-delete-row')
			.toggle(!(this.grid.df && this.grid.df.cannot_delete_rows));

		frappe.dom.freeze("", "dark");
		if (cur_frm) cur_frm.cur_grid = this;
		this.wrapper.addClass("grid-row-open");
		if (!frappe.dom.is_element_in_viewport(this.wrapper)
			&& !frappe.dom.is_element_in_modal(this.wrapper)) {
			// -15 offset to make form look visually centered
			frappe.utils.scroll_to(this.wrapper, true, -15);
		}

		if (this.frm) {
			this.frm.script_manager.trigger(this.doc.parentfield + "_on_form_rendered");
			this.frm.script_manager.trigger("form_render", this.doc.doctype, this.doc.name);
		}
	}
	hide_form() {
		frappe.dom.unfreeze();
		this.row.toggle(true);
		if (!frappe.dom.is_element_in_modal(this.row)) {
			frappe.utils.scroll_to(this.row, true, 15);
		}
		this.refresh();
		if(cur_frm) cur_frm.cur_grid = null;
		this.wrapper.removeClass("grid-row-open");
	}
	open_prev() {
		if (!this.doc) return;
		this.open_row_at_index(this.doc.idx - 2);
	}
	open_next() {
		if (!this.doc) return;

		if (!this.open_row_at_index(this.doc.idx)) {
			this.grid.add_new_row(null, null, true);
		}
	}
	open_row_at_index(row_index) {
		if (!this.grid.data[row_index]) return;

		this.change_page_if_reqd(row_index);
		this.grid.grid_rows[row_index].toggle_view(true);
		return true;
	}
	change_page_if_reqd(row_index) {
		const {
			page_index,
			page_length
		} = this.grid.grid_pagination;

		row_index++;
		let new_page;

		if (row_index <= (page_index - 1) * page_length) {
			new_page = page_index - 1;
		} else if (row_index > page_index * page_length) {
			new_page = page_index + 1;
		}

		if (new_page) {
			this.grid.grid_pagination.go_to_page(new_page);
		}
	}
	refresh_field(fieldname, txt) {
		let df = this.docfields.find(col => {
			return col.fieldname === fieldname;
		});

		// format values if no frm
		if (df && this.doc) {
			txt = frappe.format(this.doc[fieldname], df, null, this.doc);
		}

		if (!txt && this.frm) {
			txt = frappe.format(this.doc[fieldname], df, null, this.frm.doc);
		}

		// reset static value
		let column = this.columns[fieldname];
		if (column) {
			column.static_area.html(txt || "");
			if (df && df.reqd) {
				column.toggleClass('error', !!(txt === null || txt === ''));
			}
		}

		let field = this.on_grid_fields_dict[fieldname];
		// reset field value
		if (field) {
			field.docname = this.doc.name;
			field.refresh();
		}

		// in form
		if (this.grid_form) {
			this.grid_form.refresh_field(fieldname);
		}
	}
	get_field(fieldname) {
		let field = this.on_grid_fields_dict[fieldname];
		if (field) {
			return field;
		} else if(this.grid_form) {
			return this.grid_form.fields_dict[fieldname];
		} else {
			throw `fieldname ${fieldname} not found`;
		}
	}

	get_visible_columns(blacklist=[]) {
		var me = this;
		var visible_columns = $.map(this.docfields, function(df) {
			var visible = !df.hidden && df.in_list_view && me.grid.frm.get_perm(df.permlevel, "read")
				&& !in_list(frappe.model.layout_fields, df.fieldtype) && !in_list(blacklist, df.fieldname);

			return visible ? df : null;
		});
		return visible_columns;
	}
	set_field_property(fieldname, property, value) {
		// set a field property for open form / grid form
		var me = this;

		var set_property = function(field) {
			if(!field) return;
			field.df[property] = value;
			field.refresh();
		}

		// set property in grid form
		if(this.grid_form) {
			set_property(this.grid_form.fields_dict[fieldname]);
			this.grid_form.layout && this.grid_form.layout.refresh_sections();
		}

		// set property in on grid fields
		set_property(this.on_grid_fields_dict[fieldname]);
	}
	toggle_reqd(fieldname, reqd) {
		this.set_field_property(fieldname, 'reqd', reqd ? 1 : 0);
	}
	toggle_display(fieldname, show) {
		this.set_field_property(fieldname, 'hidden', show ? 0 : 1);
	}
	toggle_editable(fieldname, editable) {
		this.set_field_property(fieldname, 'read_only', editable ? 0 : 1);
	}
};
