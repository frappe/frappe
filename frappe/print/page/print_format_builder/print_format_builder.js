frappe.pfbuilder = null;

frappe.pages['print-format-builder'].onload = function(wrapper) {
	frappe.print_format_builder = new frappe.PrintFormatBuilder(wrapper);
}

frappe.pages['print-format-builder'].onshow = function(wrapper) {
	// load a new page
	if(frappe.route_options.print_format != frappe.print_format_builder.print_format) {
		frappe.print_format_builder.refresh();
	}
}

frappe.PrintFormatBuilder = Class.extend({
	init: function(parent) {
		this.parent = parent;
		this.make();
		this.refresh();
	},
	refresh: function() {
		this.print_format = frappe.route_options.print_format;
		this.visible_columns = {};

		if(!this.print_format) {
			this.as_user_to_start_from_print_format();
		} else {
			this.page.set_title(this.print_format.name);
			this.setup_print_format();
		}
	},
	make: function() {
		this.page = frappe.ui.make_app_page({
			parent: this.parent,
			title: __("Print Format Builder")
		});
	},
	as_user_to_start_from_print_format: function() {
		this.page.main.html('<div class="padding"><a class="btn btn-default btn-sm" href="#List/Print Format">'
		+__("Please create or edit a new Print Format")+'</a></div>');
	},
	setup_print_format: function() {
		var me = this;
		frappe.model.with_doctype(this.print_format.doc_type, function(doctype) {
			me.meta = frappe.get_meta(me.print_format.doc_type);
			me.setup_sidebar();
			me.render_layout();
		});
	},
	setup_sidebar: function() {
		var me = this;
		this.page.sidebar.empty();
		$(frappe.render_template("print_format_builder_sidebar",
			{fields: this.meta.fields}))
			.appendTo(this.page.sidebar);

		this.setup_field_filter();
	},
	render_layout: function() {
		this.page.main.empty();
		this.prepare_data();
		$(frappe.render_template("print_format_builder_layout", {
			data: this.layout_data, me: this}))
			.appendTo(this.page.main);
		this.setup_sortable();
		this.setup_settings();
		this.setup_column_selector();
		this.setup_add_section();
	},
	prepare_data: function() {
		this.data = JSON.parse(this.print_format.format_data || "[]");
		if(!this.data.length) {
			// new layout
			this.data = this.meta.fields;
		}
		this.layout_data = [];
		var section = null, column = null, me = this;

		// create a new placeholder for column and set
		// it as "column"
		var set_column = function() {
			column = me.get_new_column();
			section.columns.push(column);
			section.no_of_columns += 1;
		}

		// break the layout into sections and columns
		// so that it is easier to render in a template
		$.each(this.data, function(i, f) {
			if(f.fieldtype==="Section Break") {
				section = me.get_new_section();
				column = null;
				me.layout_data.push(section);

			} else if(f.fieldtype==="Column Break") {
				set_column();

			} else if(!in_list(["Section Break", "Column Break", "Fold"], f.fieldtype)
				&& !f.print_hide && f.label) {
				if(!column) set_column();

				if(f.fieldtype==="Table") {
					me.add_table_properties(f);
				}

				column.fields.push(f);
				section.has_fields = true;
			}
		});

		// strip out empty sections
		this.layout_data = $.map(this.layout_data, function(s) {
			return s.has_fields ? s : null
		});
	},
	get_new_section: function() {
		return {columns: [], no_of_columns: 0};
	},
	get_new_column: function() {
		return {fields: []}
	},
	add_table_properties: function(f) {
		var me = this;
		this.visible_columns[f.options] = [];
		$.each(frappe.get_meta(f.options).fields, function(i, _f) {
			if(!in_list(["Section Break", "Column Break"], _f.fieldtype) &&
				!_f.print_hide && f.label) {
				me.visible_columns[f.options].push(_f.fieldname);
			}
		});
	},
	setup_sortable: function() {
		var me = this;

		// drag from fields library
		Sortable.create(this.page.sidebar.find(".print-format-builder-fields").get(0),
			{
				group: {put: true, pull:"clone"},
				sort: false,
				onAdd: function(evt) {
					// on drop, trash!
					$(evt.item).fadeOut();
				}
			});

		// sort, drag and drop between columns
		this.page.main.find(".print-format-builder-column").each(function() {
			me.setup_sortable_for_column(this);
		});

		// section sorting
		Sortable.create(this.page.main.find(".print-format-builder-layout").get(0),
			{ handle: ".print-format-builder-section-head" }
		);
	},
	setup_sortable_for_column: function(col) {
		var me = this;
		Sortable.create(col, {
			group: {
				put: true,
				pull: true
			},
			onAdd: function(evt) {
				// on drop, change the HTML
				var $item = $(evt.item);
				if(!$item.hasClass("print-format-builder-field")) {
					var fieldname = $item.attr("data-fieldname"),
						field = frappe.meta.get_docfield(me.print_format.doc_type, fieldname);

					$item.replaceWith(frappe.render_template("print_format_builder_field",
						{field: field, me:me}))
				}
			}
		});

	},
	setup_field_filter: function() {
		var me = this;
		this.page.sidebar.find(".filter-fields").on("keypress", function() {
			var text = $(this).val();
			me.page.sidebar.find(".field-label").each(function() {
				var show = !text || $(this).text().toLowerCase().indexOf(text.toLowerCase())!==-1;
				$(this).parent().toggle(show);
			})
		});
	},
	setup_settings: function() {
		var me = this;
		this.page.main.on("click", ".section-settings", function() {
			var section = $(this).parent().parent();
			var no_of_columns = section.find(".section-column").length;

			// new dialog
			var d = new frappe.ui.Dialog({
				title: "Edit Section",
				fields: [
					{
						label:__("No of Columns"), fieldname:"no_of_columns",
						fieldtype:"Select", options: ["1", "2", "3"],
					},
				],
			});

			d.set_input("no_of_columns", no_of_columns + "");

			d.set_primary_action(__("Update"), function() {
				// resize number of columns
				me.update_columns_in_section(section, no_of_columns,
					cint(d.get_value("no_of_columns")));

				d.hide();
			});

			d.show();

		})
	},
	update_columns_in_section: function(section, no_of_columns, new_no_of_columns) {
		var col_size = 12 / new_no_of_columns,
			me = this,
			resize = function() {
				section.find(".section-column")
					.removeClass()
					.addClass("section-column")
					.addClass("col-md-" + col_size)
			};

		if(new_no_of_columns < no_of_columns) {
			// move contents of last n columns to previous column
			for(var i=no_of_columns; i > new_no_of_columns; i--) {
				var $col = $(section.find(".print-format-builder-column").get(i-1));
				var prev = section.find(".print-format-builder-column").get(i-2);

				// append each field to prev
				$col.parent().addClass("to-drop");
				$col.find(".print-format-builder-field").each(function() {
					$(this).appendTo(prev);
				});
			}

			// drop columns
			section.find(".to-drop").remove();

			// resize
			resize();

		} else if(new_no_of_columns > no_of_columns) {
			// add empty column and resize old columns
			for(var i=no_of_columns; i < new_no_of_columns; i++) {
				var col = $('<div class="section-column">\
					<div class="print-format-builder-column"></div></div>')
				.appendTo(section);
				me.setup_sortable_for_column(col
					.find(".print-format-builder-column").get(0));
			}
			// resize
			resize();
		}

	},
	setup_add_section: function() {
		var me = this;
		this.page.main.find(".print-format-builder-add-section").on("click", function() {
			// boostrap new section info
			var section = me.get_new_section();
			section.columns.push(me.get_new_column());
			section.no_of_columns = 1;

			var $section = $(frappe.render_template("print_format_builder_section",
            	{section: section, me: me}))
				.appendTo(me.page.main.find(".print-format-builder-layout"))

			me.setup_sortable_for_column($section.find(".print-format-builder-column").get(0));
		});
	},
	setup_column_selector: function() {
		var me = this;
		this.page.main.on("click", ".select-columns", function() {
			var parent = $(this).parent(),
				doctype = parent.attr("data-doctype"),
				label = parent.attr("data-label"),
				columns = parent.attr("data-columns").split(",");

			var d = new frappe.ui.Dialog({
				title: __("Select Table Columns for {0}", [label]),
			});

			// render checkboxes
			$(frappe.render_template("print_format_builder_column_selector", {
				fields: frappe.get_meta(doctype).fields,
				columns: columns
			})).appendTo(d.body);

			Sortable.create($(d.body).find(".column-selector-list").get(0));

			// update data-columns property on update
			d.set_primary_action(__("Update"), function() {
				me.visible_columns[doctype] = [];
				$(d.body).find("input:checked").each(function() {
					me.visible_columns[doctype].push($(this).attr("data-fieldname"));
				});
				parent.attr("data-columns", me.visible_columns[doctype].join(me.visible_columns[doctype]));
				d.hide();
			});

			d.show();
		});
	}
 });

frappe.PrintFormatField = Class.extend({
	init: function() { }
});
