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
	},

	allow_on_grid_editing: function() {
		if(frappe.utils.is_xs()) {
			return false;
		} else if(this.meta && this.meta.editable_grid || !this.meta) {
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

		this.form_grid = this.wrapper.find('.form-grid');

		this.wrapper.find(".grid-add-row").click(function() {
			me.add_new_row(null, null, true);
			me.set_focus_on_row();
			return false;
		});

		this.custom_buttons = {};
		this.grid_buttons = this.wrapper.find('.grid-buttons');
		this.remove_rows_button = this.grid_buttons.find('.grid-remove-rows')

		this.setup_allow_bulk_edit();
		this.setup_check();
		if(this.df.on_setup) {
			this.df.on_setup(this);
		}

	},
	setup_check: function() {
		var me = this;
		this.wrapper.on('click', '.grid-row-check', function(e) {
			var $check = $(this);
			if($check.parents('.grid-heading-row:first').length!==0) {
				// select all?
				var checked = $check.prop('checked');
				$check.parents('.form-grid:first')
					.find('.grid-row-check').prop('checked', checked);

				// set all
				(me.grid_rows || []).forEach(function(row) { row.doc.__checked = checked ? 1 : 0; });
			} else {
				var docname = $check.parents('.grid-row:first').attr('data-name');
				me.grid_rows_by_docname[docname].select($check.prop('checked'));
			}
			me.refresh_remove_rows_button();
		});

		this.remove_rows_button.on('click', function() {
			var dirty = false;

			let tasks = [];

			me.get_selected().forEach((docname) => {
				tasks.push(() => {
					me.grid_rows_by_docname[docname].remove();
					dirty = true;
				});
				tasks.push(() => frappe.timeout(0.1));
			});

			tasks.push(() => {
				if (dirty) me.refresh();
			});

			frappe.run_serially(tasks);
		});
	},
	select_row: function(name) {
		this.grid_rows_by_docname[name].select();
	},
	remove_all: function() {
		this.grid_rows.forEach(row => {
			row.remove();
		});
	},
	refresh_remove_rows_button: function() {
		this.remove_rows_button.toggleClass('hide',
			this.wrapper.find('.grid-body .grid-row-check:checked:first').length ? false : true);
	},
	get_selected: function() {
		return (this.grid_rows || []).map(function(row) { return row.doc.__checked ? row.doc.name : null; })
			.filter(function(d) { return d; });
	},
	get_selected_children: function() {
		return (this.grid_rows || []).map(function(row) { return row.doc.__checked ? row.doc : null; })
			.filter(function(d) { return d; });
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

		if(this.frm) {
			this.display_status = frappe.perm.get_field_display_status(this.df, this.frm.doc,
				this.perm);
		} else {
			// not in form
			this.display_status = 'Write';
		}

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
			// to hide checkbox if grid is not editable
			this.header_row && this.header_row.toggle_check();

			if(!this.grid_rows) {
				this.grid_rows = [];
			}

			this.truncate_rows(data);
			this.grid_rows_by_docname = {};

			for(var ri=0; ri < data.length; ri++) {
				var d = data[ri];

				if(d.idx===undefined) {
					d.idx = ri + 1;
				}

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
			if(this.frm && this.is_sortable() && !this.sortable_setup_done) {
				this.make_sortable($rows);
				this.sortable_setup_done = true;
			}

			this.last_display_status = this.display_status;
			this.last_docname = this.frm && this.frm.docname;
			frappe.utils.scroll_to(_scroll_y);
		}

		// red if mandatory
		this.form_grid.toggleClass('error', !!(this.df.reqd && !(data && data.length)));

		this.refresh_remove_rows_button();

		this.wrapper.trigger('change');
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
		// reset docfield
		if (this.frm && this.frm.docname) {
			// use doc specific docfield object
			this.df = frappe.meta.get_docfield(this.frm.doctype, this.df.fieldname,
				this.frm.docname);
		} else {
			// use non-doc specific docfield
			if(this.df.options) {
				this.df = frappe.meta.get_docfield(this.df.options, this.df.fieldname);
			}
		}

		if(this.doctype) {
			this.docfields = frappe.meta.get_docfields(this.doctype, this.frm.docname);
		} else {
			// fields given in docfield
			this.docfields = this.df.fields;
		}

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
				&& (this.frm && this.frm.docname==this.last_docname)
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
			group: {name: 'row'},
			handle: '.sortable-handle',
			draggable: '.grid-row',
			filter: 'li, a',
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
				me.frm.script_manager.trigger(me.df.fieldname + "_move", me.df.options, me.frm.doc[me.df.fieldname][event.newIndex].name);
				me.refresh();

				me.frm.dirty();
			}
		});

		$(this.frm.wrapper).trigger("grid-make-sortable", [this.frm]);
	},
	get_data: function() {
		var data = this.frm ?
			this.frm.doc[this.df.fieldname] || []
			: this.df.get_data();
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
		this.get_docfield(fieldname).read_only = enable ? 0 : 1;
		this.refresh();
	},
	toggle_display: function(fieldname, show) {
		this.get_docfield(fieldname).hidden = show ? 0 : 1;
		this.refresh();
	},
	get_docfield: function(fieldname) {
		return frappe.meta.get_docfield(this.doctype, fieldname, this.frm ? this.frm.docname : null);
	},
	get_row: function(key) {
		if(typeof key == 'number') {
			if(key < 0) {
				return this.grid_rows[this.grid_rows.length + key];
			} else {
				return this.grid_rows[key];
			}
		} else {
			return this.grid_rows_by_docname[key];
		}
	},
	get_grid_row: function(key) {
		return this.get_row(key);
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
			this.grid_rows_by_docname[doc.name].refresh_field(fieldname, value);
		}
	},
	add_new_row: function(idx, callback, show) {
		if(this.is_editable()) {
			if(this.frm) {
				var d = frappe.model.add_child(this.frm.doc, this.df.options, this.df.fieldname, idx);
				d.__unedited = true;
				this.frm.script_manager.trigger(this.df.fieldname + "_add", d.doctype, d.name);
				this.refresh();
			} else {
				this.df.data.push({name: "batch " + (this.df.data.length+1), idx: this.df.data.length+1});
				this.refresh();
			}

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
				.find('input[type="Text"],textarea,select').filter(':visible:first').focus();
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

			if(!df.hidden
				&& (this.editable_fields || df.in_list_view)
				&& (this.frm && this.frm.get_perm(df.permlevel, "read") || !this.frm)
				&& !in_list(frappe.model.layout_fields, df.fieldtype)) {

				if(df.columns) {
					df.colsize=df.columns;
				}
				else {
					var colsize=2;
					switch(df.fieldtype) {
						case"Text":
						case"Small Text":
							colsize=3;
							break;
						case"Check":
							colsize=1
					}
					df.colsize=colsize;
				}

				if(df.columns) {
					df.colsize=df.columns;
				}
				else {
					var colsize = 2;
					switch(df.fieldtype) {
						case "Text":
						case "Small Text": colsize = 3; break;
						case"Check": colsize = 1;
					}
					df.colsize = colsize;
				}

				total_colsize += df.colsize;
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
		return this.display_status=="Write" && !this.static_rows;
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
		if(this.frm && this.frm.get_docfield(this.df.fieldname).allow_bulk_edit) {
			// download
			me.setup_download();

			// upload
			frappe.flags.no_socketio = true;
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

										if(df.fieldtype==="Int" || df.fieldtype==="Check") {
											value = cint(value);
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
		let title = me.df.label || frappe.model.unscrub(me.df.fieldname);
		$(this.wrapper).find(".grid-download").removeClass("hide").on("click", function() {
			var data = [];
			var docfields = [];
			data.push([__("Bulk Edit {0}", [title])]);
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
				var row = [];
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

			frappe.tools.downloadify(data, null, title);
			return false;
		});
	},
	add_custom_button: function(label, click) {
		// add / unhide a custom button
		var btn = this.custom_buttons[label];
		if(!btn) {
			btn = $('<button class="btn btn-default btn-xs btn-custom">' + label + '</button>')
				.css('margin-right', '4px')
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
