// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

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


frappe.ui.form.Grid = Class.extend({
	init: function(opts) {
		var me = this;
		$.extend(this, opts);
		this.fieldinfo = {};
		this.doctype = this.df.options;
		this.meta = frappe.get_meta(this.doctype);
		this.fields_map = {};
		this.template = null;
		this.multiple_set = false;
		if(this.frm.meta.__form_grid_templates
			&& this.frm.meta.__form_grid_templates[this.df.fieldname]) {
				this.template = this.frm.meta.__form_grid_templates[this.df.fieldname];
		}

		this.is_grid = true;
	},

	allow_on_grid_editing: function() {
		if(frappe.utils.is_xs()) {
			return false;
		} else if(this.meta.editable_grid) {
			return true;
		} else {
			return false;
		}
	},
	make: function() {
		var me = this;

		this.wrapper = $(frappe.render_template("grid_body", {}))
			.appendTo(this.parent)
			.attr("data-fieldname", this.df.fieldname);

		this.wrapper.find(".grid-add-row").click(function() {
			me.add_new_row(null, null, true);
			me.set_focus_on_row();
			return false;
		});

		this.custom_buttons = {};
		this.grid_buttons = this.wrapper.find('.grid-buttons');

		this.setup_allow_bulk_edit();

	},
	make_head: function() {
		// labels
		if(!this.header_row) {
			this.header_row = new frappe.ui.form.GridRow({
				parent: $(this.parent).find(".grid-heading-row"),
				parent_df: this.df,
				docfields: this.docfields,
				frm: this.frm,
				grid: this
			});
		}
	},
	refresh: function(force) {
		!this.wrapper && this.make();
		var me = this,
			$rows = $(me.parent).find(".rows"),
			data = this.get_data();

		this.setup_fields();
		this.display_status = frappe.perm.get_field_display_status(this.df, this.frm.doc,
			this.perm);

		if(this.display_status==="None") return;

		if(!force && this.data_rows_are_same(data)) {
			// soft refresh
			this.header_row && this.header_row.refresh();
			for(var i in this.grid_rows) {
				this.grid_rows[i].refresh();
			}
		} else {
			// redraw
			var _scroll_y = $(document).scrollTop();

			this.make_head();

			if(!this.grid_rows) {
				this.grid_rows = [];
			}

			this.truncate_rows(data);
			this.grid_rows_by_docname = {};


			for(var ri=0;ri < data.length; ri++) {
				var d = data[ri];

				if(this.grid_rows[ri]) {
					var grid_row = this.grid_rows[ri];
					grid_row.doc = d;
					grid_row.refresh();
				} else {
					var grid_row = new frappe.ui.form.GridRow({
						parent: $rows,
						parent_df: this.df,
						docfields: this.docfields,
						doc: d,
						frm: this.frm,
						grid: this
					});
					this.grid_rows.push(grid_row);
				}

				this.grid_rows_by_docname[d.name] = grid_row;
			}

			this.wrapper.find(".grid-empty").toggleClass("hide", !!data.length);

			// toolbar
			this.setup_toolbar();

			// sortable
			if(this.is_sortable() && !this.sortable_setup_done) {
				this.make_sortable($rows);
				this.sortable_setup_done = true;
			}

			this.last_display_status = this.display_status;
			this.last_docname = this.frm.docname;
			frappe.utils.scroll_to(_scroll_y);
		}
	},
	setup_toolbar: function() {
		if(this.is_editable()) {
			this.wrapper.find(".grid-footer").toggle(true);

			// show, hide buttons to add rows
			if(this.cannot_add_rows) {
				// add 'hide' to buttons
				this.wrapper.find(".grid-add-row, .grid-add-multiple-rows")
					.addClass('hide');
			} else {
				// show buttons
				this.wrapper.find(".grid-add-row").removeClass('hide');

				if(this.multiple_set) {
					this.wrapper.find(".grid-add-multiple-rows").removeClass('hide')
				}
			}

		} else {
			this.wrapper.find(".grid-footer").toggle(false);
		}

	},
	truncate_rows: function(data) {
		if(this.grid_rows.length > data.length) {
			// remove extra rows
			for(var i=data.length; i < this.grid_rows.length; i++) {
				var grid_row = this.grid_rows[i];
				grid_row.wrapper.remove();
			}
			this.grid_rows.splice(data.length);
		}
	},
	setup_fields: function() {
		var me = this;
		if (this.frm && this.frm.docname) {
			// use doc specific docfield object
			this.df = frappe.meta.get_docfield(this.frm.doctype, this.df.fieldname,
					this.frm.docname);
		} else {
			// use non-doc specific docfield
			this.df = frappe.meta.get_docfield(this.df.options, this.df.fieldname);
		}

		this.docfields = frappe.meta.get_docfields(this.doctype, this.frm.docname);

		this.docfields.forEach(function(df) {
			me.fields_map[df.fieldname] = df;
		});
	},
	refresh_row: function(docname) {
		this.grid_rows_by_docname[docname] &&
			this.grid_rows_by_docname[docname].refresh();
	},
	data_rows_are_same: function(data) {
		if(this.grid_rows) {
			var same = data.length==this.grid_rows.length
				&& this.display_status==this.last_display_status
				&& this.frm.docname==this.last_docname
				&& !$.map(this.grid_rows, function(g, i) {
					return (g && g.doc && g.doc.name==data[i].name) ? null : true;
				}).length;

			return same;
		}
	},
	make_sortable: function($rows) {
		var me =this;
		if ('ontouchstart' in window) {
			return;
		}

		new Sortable($rows.get(0), {
			handle: ".sortable-handle",
			onUpdate: function(event, ui) {
				me.frm.doc[me.df.fieldname] = [];
				$rows.find(".grid-row").each(function(i, item) {
					var doc = locals[me.doctype][$(item).attr('data-name')];
					doc.idx = i + 1;
					me.frm.doc[me.df.fieldname].push(doc);
				});

				// re-order grid-rows by name
				me.grid_rows = [];
				me.frm.doc[me.df.fieldname].forEach(function(d) {
					me.grid_rows.push(me.grid_rows_by_docname[d.name]);
				});

				me.refresh();

				me.frm.dirty();
			}
		});

		$(this.frm.wrapper).trigger("grid-make-sortable", [this.frm]);
	},
	get_data: function() {
		var data = this.frm.doc[this.df.fieldname] || [];
		data.sort(function(a, b) { return a.idx - b.idx});
		return data;
	},
	set_column_disp: function(fieldname, show) {
		if($.isArray(fieldname)) {
			var me = this;
			for(var i=0, l=fieldname.length; i<l; i++) {
				var fname = fieldname[i];
				me.get_docfield(fname).hidden = show ? 0 : 1;
			}
		} else {
			this.get_docfield(fieldname).hidden = show ? 0 : 1;
		}

		this.refresh(true);
	},
	toggle_reqd: function(fieldname, reqd) {
		this.get_docfield(fieldname).reqd = reqd;
		this.refresh();
	},
	toggle_enable: function(fieldname, enable) {
		this.get_docfield(fieldname).read_only = enable ? 0 : 1;;
		this.refresh();
	},
	get_docfield: function(fieldname) {
		return frappe.meta.get_docfield(this.doctype, fieldname, this.frm ? this.frm.docname : null);
	},
	get_grid_row: function(docname) {
		return this.grid_rows_by_docname[docname];
	},
	get_field: function(fieldname) {
		// Note: workaround for get_query
		if(!this.fieldinfo[fieldname])
			this.fieldinfo[fieldname] = {
			}
		return this.fieldinfo[fieldname];
	},
	set_value: function(fieldname, value, doc) {
		if(this.display_status!=="None" && this.grid_rows_by_docname[doc.name]) {
			this.grid_rows_by_docname[doc.name].refresh_field(fieldname);
		}
	},
	add_new_row: function(idx, callback, show) {
		if(this.is_editable()) {
			var d = frappe.model.add_child(this.frm.doc, this.df.options, this.df.fieldname, idx);
			d.__unedited = true;
			this.frm.script_manager.trigger(this.df.fieldname + "_add", d.doctype, d.name);
			this.refresh();

			if(show) {
				if(idx) {
					// always open inserted rows
					this.wrapper.find("[data-idx='"+idx+"']").data("grid_row")
						.toggle_view(true, callback);
				} else {
					if(!this.allow_on_grid_editing()) {
						// open last row only if on-grid-editing is disabled
						this.wrapper.find(".grid-row:last").data("grid_row")
							.toggle_view(true, callback);
					}
				}
			}

			return d;
		}
	},

	set_focus_on_row: function(idx) {
		var me = this;
		if(!idx) {
			idx = me.grid_rows.length - 1;
		}
		setTimeout(function() {
			me.grid_rows[idx].row
				.find('input,textarea,select').filter(':visible:first').focus();
		}, 100);
	},

	setup_visible_columns: function() {
		if(this.visible_columns) return;

		var total_colsize = 1,
			fields = this.editable_fields || this.docfields;

		this.visible_columns = [];

		for(var ci in fields) {
			var _df = fields[ci];

			// get docfield if from fieldname
			df = this.fields_map[_df.fieldname];

			if(!df) {
				throw 'field not found: ' + _df.fieldname;
			}

			if(!df.hidden
				&& (this.editable_fields || df.in_list_view)
				&& this.frm.get_perm(df.permlevel, "read")
				&& !in_list(frappe.model.layout_fields, df.fieldtype)) {
					if(df.columns) {
						df.colsize=df.columns;
					}	
					else {
						var colsize=2;
						switch(df.fieldtype){
							case"Text":
							case"Small Text":
								colsize=3;
								break;
							case"Check":
								colsize=1
							}
							df.colsize=colsize
					}

					total_colsize += df.colsize
					if(total_colsize > 11)
						return false;
					this.visible_columns.push([df, df.colsize]);
				}
		}

		// redistribute if total-col size is less than 12
		var passes = 0;
		while(total_colsize < 11 && passes < 12) {
			for(var i in this.visible_columns) {
				var df = this.visible_columns[i][0];
				var colsize = this.visible_columns[i][1];
				if(colsize > 1 && colsize < 11
					&& !in_list(frappe.model.std_fields_list, df.fieldname)) {

					if (passes < 3 && ["Int", "Currency", "Float", "Check", "Percent"].indexOf(df.fieldtype)!==-1) {
						// don't increase col size of these fields in first 3 passes
						continue;
					}

					this.visible_columns[i][1] += 1;
					total_colsize++;
				}

				if(total_colsize > 10)
					break;
			}
			passes++;
		}
	},


	is_editable: function() {
		return this.display_status=="Write" && !this.static_rows
	},
	is_sortable: function() {
		return this.sortable_status || this.is_editable();
	},
	only_sortable: function(status) {
		if(status===undefined ? true : status) {
			this.sortable_status = true;
			this.static_rows = true;
		}
	},
	set_multiple_add: function(link, qty) {
		if(this.multiple_set) return;
		var me = this;
		var link_field = frappe.meta.get_docfield(this.df.options, link);
		var btn = $(this.wrapper).find(".grid-add-multiple-rows");

		// show button
		btn.removeClass('hide');

		// open link selector on click
		btn.on("click", function() {
			new frappe.ui.form.LinkSelector({
				doctype: link_field.options,
				fieldname: link,
				qty_fieldname: qty,
				target: me,
				txt: ""
			});
			return false;
		});
		this.multiple_set = true;
	},
	setup_allow_bulk_edit: function() {
		var me = this;
		if(this.frm.get_docfield(this.df.fieldname).allow_bulk_edit) {
			// download
			me.setup_download();

			// upload
			$(this.wrapper).find(".grid-upload").removeClass("hide").on("click", function() {
				frappe.prompt({fieldtype:"Attach", label:"Upload File"},
					function(data) {
						var data = frappe.utils.csv_to_array(frappe.upload.get_string(data.upload_file));
						// row #2 contains fieldnames;
						var fieldnames = data[2];

						me.frm.clear_table(me.df.fieldname);
						$.each(data, function(i, row) {
							if(i > 4) {
								var blank_row = true;
								$.each(row, function(ci, value) {
									if(value) {
										blank_row = false;
										return false;
									}
								});

								if(!blank_row) {
									var d = me.frm.add_child(me.df.fieldname);
									$.each(row, function(ci, value) {
										var fieldname = fieldnames[ci];
										var df = frappe.meta.get_docfield(me.df.options, fieldname);

										// convert date formatting
										if(df.fieldtype==="Date" && value) {
											value = frappe.datetime.user_to_str(value);
										}
										d[fieldnames[ci]] = value;
									});
								}
							}
						});

						me.frm.refresh_field(me.df.fieldname);
						frappe.msgprint({message:__('Table updated'), title:__('Success'), indicator:'green'})

					}, __("Edit via Upload"), __("Update"));
				return false;
			});
		}
	},
	setup_download: function() {
		var me = this;
		$(this.wrapper).find(".grid-download").removeClass("hide").on("click", function() {
			var data = [];
			var docfields = [];
			data.push([__("Bulk Edit {0}", [me.df.label])]);
			data.push([]);
			data.push([]);
			data.push([]);
			data.push(["------"]);
			$.each(frappe.get_meta(me.df.options).fields, function(i, df) {
				if(frappe.model.is_value_type(df.fieldtype)) {
					data[1].push(df.label);
					data[2].push(df.fieldname);
					data[3].push(df.description || "");
					docfields.push(df);
				}
			});

			// add data
			$.each(me.frm.doc[me.df.fieldname] || [], function(i, d) {
				row = [];
				$.each(data[2], function(i, fieldname) {
					var value = d[fieldname];

					// format date
					if(docfields[i].fieldtype==="Date" && value) {
						value = frappe.datetime.str_to_user(value);
					}

					row.push(value || "");
				});
				data.push(row);
			});

			frappe.tools.downloadify(data, null, me.df.label);
			return false;
		});
	},
	add_custom_button: function(label, click) {
		// add / unhide a custom button
		var btn = this.custom_buttons[label];
		if(!btn) {
			btn = $('<button class="btn btn-default btn-xs btn-custom">' + label + '</button>')
				.css('margin-right', '10px')
				.prependTo(this.grid_buttons)
				.on('click', click);
			this.custom_buttons[label] = btn;
		} else {
			btn.removeClass('hidden');
		}
	},
	clear_custom_buttons: function() {
		// hide all custom buttons
		this.grid_buttons.find('.btn-custom').addClass('hidden');
	}
});

frappe.ui.form.GridRow = Class.extend({
	init: function(opts) {
		this.on_grid_fields_dict = {};
		this.on_grid_fields = [];
		this.columns = {};
		this.columns_list = [];
		$.extend(this, opts);
		this.make();
	},
	make: function() {
		var me = this;
		this.wrapper = $('<div class="grid-row"></div>').appendTo(this.parent).data("grid_row", this);
		this.row = $('<div class="data-row row sortable-handle"></div>').appendTo(this.wrapper)
			.on("click", function() {
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
	},
	set_data: function() {
		this.wrapper.data({
			"doc": this.doc
		})
	},
	set_row_index: function() {
		if(this.doc) {
			this.wrapper
				.attr('data-name', this.doc.name)
				.attr("data-idx", this.doc.idx)
				.find(".row-index, .grid-form-row-index").html(this.doc.idx)

		}
	},
	remove: function() {
		if(this.grid.is_editable()) {
			if(this.get_open_form()) {
				this.hide_form();
			}

			this.frm.script_manager.trigger("before_" + this.grid.df.fieldname + "_remove",
				this.doc.doctype, this.doc.name);

			//this.wrapper.toggle(false);
			frappe.model.clear_doc(this.doc.doctype, this.doc.name);

			this.frm.script_manager.trigger(this.grid.df.fieldname + "_remove",
				this.doc.doctype, this.doc.name);
			this.frm.dirty();
			this.grid.refresh();
		}
	},
	insert: function(show) {
		var idx = this.doc.idx;
		this.toggle_view(false);
		this.grid.add_new_row(idx, null, show);
	},
	refresh: function() {
		if(this.doc) {
			this.doc = locals[this.doc.doctype][this.doc.name];
		}
		// re write columns
		this.visible_columns = null;

		if(this.grid.template && !this.grid.meta.editable_grid) {
			this.render_template();
		} else {
			this.render_row(true);
		}

		// refersh form fields
		if(this.grid_form) {
			this.grid_form.layout && this.grid_form.layout.refresh(this.doc);
		}
	},
	render_template: function() {
		if(this.row_display) {
			this.row_display.remove();
		}
		var index_html = '';

		// row index
		if(this.doc) {
			if(!this.row_index) {
				this.row_index = $('<div style="float: left; margin-left: 15px; margin-top: 8px; \
					margin-right: -20px;"></div>').appendTo(this.row);
			}
			this.row_index.html(this.doc.idx);
		}

		this.row_display = $('<div class="row-data template-row">'+
			+'</div>').appendTo(this.row)
			.html(frappe.render(this.grid.template, {
				doc: this.doc ? frappe.get_format_helper(this.doc) : null,
				frm: this.frm,
				row: this
			}));
	},
	render_row: function(refresh) {
		var me = this;
		this.set_row_index();

		// index (1, 2, 3 etc)
		if(!this.row_index) {
			this.row_index = $('<div class="row-index col col-xs-1">' + (this.doc ? this.doc.idx : "&nbsp;")+ '</div>')
				.appendTo(this.row)
				.on('click', function() { me.toggle_view(); });
		} else {
			this.row_index.html(this.doc ? this.doc.idx : "&nbsp;");
		}

		this.setup_columns();
		this.add_open_form_button();

		if(this.doc) {
			$(this.frm.wrapper).trigger("grid-row-render", [this]);
		}
	},

	make_editable: function() {
		this.row.toggleClass('editable-row', this.grid.is_editable());
	},

	add_open_form_button: function() {
		var me = this;
		if(this.doc) {
			// remove row
			if(!this.open_form_button) {
				this.open_form_button = $('<a class="close btn-open-row">\
					<span class="octicon octicon-triangle-down"></span></a>')
					.appendTo($('<div class="col col-xs-1"></div>').appendTo(this.row))
					.on('click', function() { me.toggle_view(); return false; });

				if(this.row.width() < 400) {
					// narrow
					this.open_form_button.css({'margin-right': '-2px'});
				}
			}
		}
	},

	setup_columns: function() {
		var me = this;
		this.focus_set = false;
		this.grid.setup_visible_columns();

		for(var ci in this.grid.visible_columns) {
			var df = this.grid.visible_columns[ci][0],
				colsize = this.grid.visible_columns[ci][1],
				txt = this.doc ?
					frappe.format(this.doc[df.fieldname], df, null, this.doc) :
					__(df.label);

			if(this.doc && df.fieldtype === "Select") {
				txt = __(txt);
			}

			if(!this.columns[df.fieldname]) {
				var column = this.make_column(df, colsize, txt, ci);
			} else {
				var column = this.columns[df.fieldname];
				this.refresh_field(df.fieldname, txt);
			}

		}

	},

	make_column: function(df, colsize, txt, ci) {
		var	me = this;
		var add_class = ((["Text", "Small Text"].indexOf(df.fieldtype)!==-1) ?
			" grid-overflow-no-ellipsis" : "");
		add_class += (["Int", "Currency", "Float", "Percent"].indexOf(df.fieldtype)!==-1) ?
			" text-right": "";
		add_class += (["Check"].indexOf(df.fieldtype)!==-1) ?
			" text-center": "";

		$col = $('<div class="col grid-static-col col-xs-'+colsize+' '+add_class+'"></div>')
			.attr("data-fieldname", df.fieldname)
			.attr("data-fieldtype", df.fieldtype)
			.data("df", df)
			.appendTo(this.row)
			.on('click', function() {
				if(frappe.ui.form.editable_row===me) {
					return;
				}
				out = me.toggle_editable_row();
				var col = this;
				setTimeout(function() {
					$(col).find(':input:first').focus();
				}, 500);
				return out;
			});

		$col.field_area = $('<div class="field-area"></div>').appendTo($col).toggle(false);
		$col.static_area = $('<div class="static-area text-ellipsis"></div>').appendTo($col).html(txt);
		$col.df = df;
		$col.column_index = ci;

		this.columns[df.fieldname] = $col;
		this.columns_list.push($col);

		return $col;
	},

	toggle_editable_row: function(show) {
		var me = this;
		// show static for field based on
		// whether grid is editable
		if(this.grid.allow_on_grid_editing() && this.grid.is_editable() && this.doc && show !== false) {

			// disable other editale row
			if(frappe.ui.form.editable_row
				&& frappe.ui.form.editable_row !== this) {
				frappe.ui.form.editable_row.toggle_editable_row(false);
			};

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
			this.columns_list.forEach(function(column) {
				column.static_area.toggle(true);
				column.field_area && column.field_area.toggle(false);
			});
			frappe.ui.form.editable_row = null;
		}
	},


	make_control: function(column) {
		if(column.field) return;

		var me = this,
			parent = column.field_area,
			df = column.df;


		// no text editor in grid
		if (df.fieldtype=='Text Editor') {
			df.fieldtype = 'Text';
		}

		var field = frappe.ui.form.make_control({
			df: df,
			parent: parent,
			only_input: true,
			with_link_btn: true,
			doctype: this.doc.doctype,
			docname: this.doc.name,
			frm: this.grid.frm
		});

		// sync get_query
		field.get_query = this.grid.get_field(df.fieldname).get_query;
		field.refresh();
		if(field.$input) {
			field.$input.addClass('input-sm');
			field.$input
				.attr('data-col-idx', column.column_index)
				.attr('placeholder', __(df.label));
		}
		this.set_arrow_keys(field);
		column.field = field;
		this.on_grid_fields_dict[df.fieldname] = field;
		this.on_grid_fields.push(field);

	},

	set_arrow_keys: function(field) {
		var me = this;
		if(field.$input) {
			field.$input.on('keydown', function(e) {
				var values = me.frm.doc[me.grid.df.fieldname];
				var fieldname = $(this).attr('data-fieldname');
				// TAB
				if(e.which==TAB) {
					// last column
					if(me.grid.wrapper.find('input:enabled:last').get(0)===this) {
						setTimeout(function() {
							if(me.doc.idx === values.length) {
								// last row
								me.grid.add_new_row(null, null, true);
								me.grid.grid_rows[me.grid.grid_rows.length - 1].toggle_editable_row();
								me.grid.set_focus_on_row();
							} else {
								me.grid.grid_rows[me.doc.idx].toggle_editable_row();
								me.grid.set_focus_on_row(me.doc.idx+1);
							}
						}, 500);
					}
				} else if(e.which==UP_ARROW) {
					if(me.doc.idx > 1) {
						var prev = me.grid.grid_rows[me.doc.idx-2];
						prev.toggle_editable_row();
						setTimeout(function() {
							var input = prev.columns[fieldname].field.$input;
							if(input) {
								input.focus();
							}
						}, 400)
					}
				} else if(e.which==DOWN_ARROW) {
					if(me.doc.idx < values.length) {
						var next = me.grid.grid_rows[me.doc.idx];
						next.toggle_editable_row();
						setTimeout(function() {
							var input = next.columns[fieldname].field.$input;
							if(input) {
								input.focus();
							}
						}, 400)
					}
				}

			});
		}
	},

	get_open_form: function() {
		return frappe.ui.form.get_open_grid_form();
	},

	toggle_view: function(show, callback) {
		if(!this.doc) {
			return this;
		}

		this.doc = locals[this.doc.doctype][this.doc.name];
		// hide other
		var open_row = this.get_open_form();

		if (show===undefined) show = !!!open_row;

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
	},
	show_form: function() {
		if(!this.grid_form) {
			this.grid_form = new frappe.ui.form.GridRowForm({
				row: this
			});
		}
		this.grid_form.render();
		this.row.toggle(false);
		// this.form_panel.toggle(true);
		frappe.dom.freeze("", "dark");
		cur_frm.cur_grid = this;
		this.wrapper.addClass("grid-row-open");
		if(!frappe.dom.is_element_in_viewport(this.wrapper)) {
			frappe.utils.scroll_to(this.wrapper, true, 15);
		}
		this.frm.script_manager.trigger(this.doc.parentfield + "_on_form_rendered");
		this.frm.script_manager.trigger("form_render", this.doc.doctype, this.doc.name);
	},
	hide_form: function() {
		frappe.dom.unfreeze();
		this.row.toggle(true);
		this.refresh();
		cur_frm.cur_grid = null;
		this.wrapper.removeClass("grid-row-open");
	},
	open_prev: function() {
		if(this.grid.grid_rows[this.doc.idx-2]) {
			this.grid.grid_rows[this.doc.idx-2].toggle_view(true);
		}
	},
	open_next: function() {
		if(this.grid.grid_rows[this.doc.idx]) {
			this.grid.grid_rows[this.doc.idx].toggle_view(true);
		} else {
			this.grid.add_new_row(null, null, true);
		}
	},
	refresh_field: function(fieldname, txt) {
		if(txt===undefined) {
			var txt = frappe.format(this.doc[fieldname], this.grid.get_docfield(fieldname),
				null, this.frm.doc);
		}

		// reset static value
		var column = this.columns[fieldname];
		if(column) {
			column.static_area.html(txt || "");
		}

		// reset field value
		var field = this.on_grid_fields_dict[fieldname];
		if(field) {
			field.docname = this.doc.name;
			field.refresh();
		}

		// in form
		if(this.grid_form) {
			this.grid_form.refresh_field(fieldname);
		}
	},
	get_visible_columns: function(blacklist) {
		var me = this;
		var visible_columns = $.map(this.docfields, function(df) {
			var visible = !df.hidden && df.in_list_view && me.grid.frm.get_perm(df.permlevel, "read")
				&& !in_list(frappe.model.layout_fields, df.fieldtype) && !in_list(blacklist, df.fieldname);

			return visible ? df : null;
		});
		return visible_columns;
	},
	set_field_property: function(fieldname, property, value) {
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
	},
	toggle_reqd: function(fieldname, reqd) {
		this.set_field_property(fieldname, 'reqd', reqd ? 1 : 0);
	},
	toggle_display: function(fieldname, show) {
		this.set_field_property(fieldname, 'hidden', show ? 0 : 1);
	},
	toggle_editable: function(fieldname, editable) {
		this.set_field_property(fieldname, 'read_only', editable ? 0 : 1);
	},
});

frappe.ui.form.GridRowForm = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.wrapper = $('<div class="form-in-grid"></div>')
			.appendTo(this.row.wrapper);

	},
	render: function() {
		var me = this;
		this.make_form();
		this.form_area.empty();

		this.layout = new frappe.ui.form.Layout({
			fields: this.row.docfields,
			body: this.form_area,
			no_submit_on_enter: true,
			frm: this.row.frm,
		});
		this.layout.make();

		this.fields = this.layout.fields;
		this.fields_dict = this.layout.fields_dict;

		this.layout.refresh(this.row.doc);

		// copy get_query to fields
		for(var fieldname in (this.row.grid.fieldinfo || {})) {
			var fi = this.row.grid.fieldinfo[fieldname];
			$.extend(me.fields_dict[fieldname], fi);
		}

		this.toggle_add_delete_button_display(this.wrapper);

		this.row.grid.open_grid_row = this;

		this.set_focus();
	},
	make_form: function() {
		if(!this.form_area) {
			$(frappe.render_template("grid_form", {grid:this})).appendTo(this.wrapper);
			this.form_area = this.wrapper.find(".form-area");
			this.row.set_row_index();
			this.set_form_events();
		}
	},
	set_form_events: function() {
		var me = this;
		this.wrapper.find(".grid-delete-row")
			.click(function() { me.row.remove(); return false; })
		this.wrapper.find(".grid-insert-row")
			.click(function() { me.row.insert(true); return false; })
		this.wrapper.find(".grid-append-row")
			.click(function() {
				me.row.toggle_view(false);
				me.row.grid.add_new_row(me.row.doc.idx+1, null, true);
				return false;
		})
		this.wrapper.find(".grid-form-heading, .grid-footer-toolbar").on("click", function() {
			me.row.toggle_view();
			return false;
		});
	},
	toggle_add_delete_button_display: function($parent) {
		$parent.find(".grid-delete-row, .grid-insert-row, .grid-append-row")
			.toggle(this.row.grid.is_editable());
	},
	refresh_field: function(fieldname) {
		if(this.fields_dict[fieldname]) {
			this.fields_dict[fieldname].refresh();
			this.layout && this.layout.refresh_dependency();
		}
	},
	set_focus: function() {
		// wait for animation and then focus on the first row
		var me = this;
		setTimeout(function() {
			if(me.row.frm.doc.docstatus===0) {
				var first = me.form_area.find(":input:first");
				if(first.length && !in_list(["Date", "Datetime", "Time"], first.attr("data-fieldtype"))) {
					try {
						first.get(0).focus();
					} catch(e) {
						//
					}
				}
			}
		}, 500);
	},
});
