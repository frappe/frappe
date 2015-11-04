frappe.pages['print-format-builder'].on_page_load = function(wrapper) {
	frappe.print_format_builder = new frappe.PrintFormatBuilder(wrapper);
	frappe.breadcrumbs.add("Setup", "Print Format");
}

frappe.pages['print-format-builder'].on_page_show = function(wrapper) {
	if(frappe.route_options) {
		if(frappe.route_options.make_new) {
			var doctype = frappe.route_options.doctype;
			var name = frappe.route_options.name;
			frappe.route_options = null;
			frappe.print_format_builder.setup_new_print_format(doctype, name);
		} else {
			frappe.print_format_builder.print_format = frappe.route_options.doc;
			frappe.route_options = null;
			frappe.print_format_builder.refresh();
		}
	}
}

frappe.PrintFormatBuilder = Class.extend({
	init: function(parent) {
		this.parent = parent;
		this.make();
		this.refresh();
	},
	refresh: function() {
		if(!this.print_format) {
			this.show_start();
		} else {
			this.page.set_title(this.print_format.name);
			this.setup_print_format();
		}
	},
	make: function() {
		this.page = frappe.ui.make_app_page({
			parent: this.parent,
			title: __("Print Format Builder"),
			single_column: true
		});

		this.page.main.css({"border-color": "transparent"});

		this.page.sidebar = $('<div class="print-format-builder-sidebar"></div>').appendTo(this.page.main);
		this.page.main = $('<div class="border print-format-builder-main" \
			style="width: calc(100% - 160px);"></div>').appendTo(this.page.main);

		// future-bindings for buttons on sections / fields
		// bind only once
		this.setup_section_settings();
		this.setup_column_selector();
		this.setup_edit_custom_html();
		// $(this.page.sidebar).css({"position": 'fixed'});
		// $(this.page.main).parent().css({"margin-left": '16.67%'});
	},
	show_start: function() {
		this.page.main.html(frappe.render_template("print_format_builder_start", {}));
		this.page.sidebar.html("");
		this.page.clear_actions();
		this.page.set_title(__("Print Format Builder"));
		this.start_edit_print_format();
		this.start_new_print_format();
	},
	start_edit_print_format: function() {
		// print format control
		var me = this;
		this.print_format_input = frappe.ui.form.make_control({
			parent: this.page.main.find(".print-format-selector"),
			df: {
				fieldtype: "Link",
				options: "Print Format",
				filters: {
					print_format_builder: 1
				},
				label: __("Select Print Format to Edit"),
				only_select: true
			},
			render_input: true
		});

		// create a new print format.
		this.page.main.find(".btn-edit-print-format").on("click", function() {
			var name = me.print_format_input.get_value();
			if(!name) return;
			frappe.model.with_doc("Print Format", name, function(doc) {
				me.print_format = frappe.get_doc("Print Format", name);
				me.refresh();
			});
		});
	},
	start_new_print_format: function() {
		var me = this;
		this.doctype_input = frappe.ui.form.make_control({
			parent: this.page.main.find(".doctype-selector"),
			df: {
				fieldtype: "Link",
				options: "DocType",
				filters: {
					"istable": 0,
					"issingle": 0
				},
				label: __("Select a DocType to make a new format")
			},
			render_input: true
		});

		this.name_input = frappe.ui.form.make_control({
			parent: this.page.main.find(".name-selector"),
			df: {
				fieldtype: "Data",
				label: __("Name of the new Print Format"),
			},
			render_input: true
		});

		this.page.main.find(".btn-new-print-format").on("click", function() {
			var doctype = me.doctype_input.get_value(),
				name = me.name_input.get_value();
			if(!(doctype && name)) {
				msgprint(__("Both DocType and Name required"));
				return;
			}
			me.setup_new_print_format(doctype, name);

		});
	},
	setup_new_print_format: function(doctype, name) {
		var me = this;
		frappe.call({
			method: "frappe.client.insert",
			args: {
				doc: {
					doctype: "Print Format",
					name: name,
					standard: "No",
					doc_type: doctype,
					print_format_builder: 1
				}
			},
			callback: function(r) {
				me.print_format = r.message;
				me.refresh();
			}
		});
	},
	setup_print_format: function() {
		var me = this;
		frappe.model.with_doctype(this.print_format.doc_type, function(doctype) {
			me.meta = frappe.get_meta(me.print_format.doc_type);
			me.setup_sidebar();
			me.render_layout();
			me.page.set_primary_action(__("Save"), function() {
				me.save_print_format();
			});
			me.page.clear_menu();
			me.page.add_menu_item(__("Start new Format"), function() {
				me.print_format = null;
				me.refresh();
			}, true);
			me.page.add_menu_item(__("Edit Properties"), function() {
				frappe.set_route("Form", "Print Format", me.print_format.name);
			}, true);
		});
	},
	setup_sidebar: function() {
		var me = this;
		this.page.sidebar.empty();

		// prepend custom HTML field
		var fields = [this.get_custom_html_field()].concat(this.meta.fields);

		$(frappe.render_template("print_format_builder_sidebar",
			{fields: fields}))
			.appendTo(this.page.sidebar);

		this.setup_field_filter();
	},
	get_custom_html_field: function() {
		return {
			fieldtype: "Custom HTML",
			fieldname: "_custom_html",
			label: __("Custom HTML")
		}
	},
	render_layout: function() {
		this.page.main.empty();
		this.prepare_data();
		$(frappe.render_template("print_format_builder_layout", {
			data: this.layout_data, me: this}))
			.appendTo(this.page.main);
		this.setup_sortable();
		this.setup_add_section();
		this.setup_edit_heading();
	},
	prepare_data: function() {
		this.print_heading_template = null;
		this.data = JSON.parse(this.print_format.format_data || "[]");
		if(!this.data.length) {
			// new layout
			this.data = this.meta.fields;
		} else {
			// extract print_heading_template if found
			if(this.data[0].fieldname==="print_heading_template") {
				this.print_heading_template = this.data[0].options;
				this.data = this.data.splice(1);
			}
		}
		this.layout_data = [];
		var section = null, column = null, me = this;

		// create a new placeholder for column and set
		// it as "column"
		var set_column = function() {
			if(!section) set_section();
			column = me.get_new_column();
			section.columns.push(column);
			section.no_of_columns += 1;
		}

		var set_section = function() {
			section = me.get_new_section();
			column = null;
			me.layout_data.push(section);
		}

		// break the layout into sections and columns
		// so that it is easier to render in a template
		$.each(this.data, function(i, f) {
			if(!f.name && f.fieldname) {
				// from format_data (designed format)
				// print_hide should always be false
				if(f.fieldname==="_custom_html") {
					f.label = "Custom HTML";
					f.fieldtype = "Custom HTML"
				} else {
					f = $.extend(frappe.meta.get_docfield(me.print_format.doc_type,
						f.fieldname) || {}, f);
				}
			}

			if(f.fieldtype==="Section Break") {
				set_section();

			} else if(f.fieldtype==="Column Break") {
				set_column();

			} else if(!in_list(["Section Break", "Column Break", "Fold"], f.fieldtype)
			 	&& f.label) {
				if(!column) set_column();

				if(f.fieldtype==="Table") {
					me.add_table_properties(f);
				}

				if(!f.print_hide) {
					column.fields.push(f);
					section.has_fields = true;
				}
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
		// build table columns and widths in a dict
		// visible_columns
		var me = this;
		if(!f.visible_columns) {
			me.init_visible_columns(f);
		}
	},
	init_visible_columns: function(f) {
		f.visible_columns = []
		$.each(frappe.get_meta(f.options).fields, function(i, _f) {
			if(!in_list(["Section Break", "Column Break"], _f.fieldtype) &&
				!_f.print_hide && f.label) {

				// column names set as fieldname|width
				f.visible_columns.push({fieldname: _f.fieldname,
					print_width: (_f.width || ""), print_hide:0});
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
					var fieldname = $item.attr("data-fieldname");

					if(fieldname==="_custom_html") {
						var field = me.get_custom_html_field();
					} else {
						var field = frappe.meta.get_docfield(me.print_format.doc_type, fieldname);
					}

					$item.replaceWith(frappe.render_template("print_format_builder_field",
						{field: field, me:me}))
				}
			}
		});

	},
	setup_field_filter: function() {
		var me = this;
		this.page.sidebar.find(".filter-fields").on("keyup", function() {
			var text = $(this).val();
			me.page.sidebar.find(".field-label").each(function() {
				var show = !text || $(this).text().toLowerCase().indexOf(text.toLowerCase())!==-1;
				$(this).parent().toggle(show);
			})
		});
	},
	setup_section_settings: function() {
		var me = this;
		this.page.main.on("click", ".section-settings", function() {
			var section = $(this).parent().parent();
			var no_of_columns = section.find(".section-column").length;

			// new dialog
			var d = new frappe.ui.Dialog({
				title: "Edit Section",
				fields: [
					{
						label:__("No of Columns"),
						fieldname:"no_of_columns",
						fieldtype:"Select",
						options: ["1", "2", "3"],
					},
					{
						label: __("Remove Section"),
						fieldname: "remove_section",
						fieldtype: "Button",
						click: function() {
							d.hide();
							section.fadeOut(function() {section.remove()});
						},
						input_class: "btn-danger",
						input_css: {
							"margin-top": "20px"
						}
					}
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

			return false;
		});
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
	setup_edit_heading: function() {
		var me = this;
		this.page.main.find(".edit-heading").on("click", function() {
			var $heading = $(this).parents(".print-format-builder-header:first")
				.find(".print-format-builder-print-heading");
			var d = me.get_edit_html_dialog(__("Edit Heading"), __("Heading"), $heading);
		})
	},
	setup_column_selector: function() {
		var me = this;
		this.page.main.on("click", ".select-columns", function() {
			var parent = $(this).parents(".print-format-builder-field:first"),
				doctype = parent.attr("data-doctype"),
				label = parent.attr("data-label"),
				columns = parent.attr("data-columns").split(",")
				column_names = $.map(columns, function(v) { return v.split("|")[0]; });
				widths = {};

			$.each(columns, function(i, v) {
				var parts = v.split("|");
				widths[parts[0]] = parts[1] || "";
			});

			var d = new frappe.ui.Dialog({
				title: __("Select Table Columns for {0}", [label]),
			});

			var $body = $(d.body);

			// render checkboxes
			$(frappe.render_template("print_format_builder_column_selector", {
				fields: frappe.get_meta(doctype).fields,
				column_names: column_names,
				widths: widths
			})).appendTo(d.body);

			Sortable.create($body.find(".column-selector-list").get(0));

			var get_width_input = function(fieldname) {
				return $body.find(".column-width[data-fieldname='"+ fieldname +"']")
			}

			// update data-columns property on update
			d.set_primary_action(__("Update"), function() {
				var visible_columns = [];
				$body.find("input:checked").each(function() {
					var fieldname = $(this).attr("data-fieldname"),
						width = get_width_input(fieldname).val() || "";
					visible_columns.push(fieldname + "|" + width);
				});
				parent.attr("data-columns", visible_columns.join(","));
				d.hide();
			});

			// enable / disable input based on selection
			$body.on("click", "input[type='checkbox']", function() {
				var disabled = !$(this).prop("checked"),
					input = get_width_input($(this).attr("data-fieldname"));

				input.prop("disabled", disabled);
				if(disabled) input.val("");
			});

			d.show();

			return false;
		});
	},
	get_visible_columns_string: function(f) {
		if(!f.visible_columns) {
			this.init_visible_columns(f);
		}
		return $.map(f.visible_columns, function(v) { return v.fieldname + "|" + (v.print_width || "") }).join(",");
	},
	get_no_content: function() {
		return '<div class="text-extra-muted" data-no-content>'+__("Edit to add content")+'</div>'
	},
	setup_edit_custom_html: function() {
		var me = this;
		this.page.main.on("click", ".edit-html", function() {
			me.get_edit_html_dialog(__("Edit Custom HTML"), __("Custom HTML"),
				$(this).parents(".print-format-builder-field:first").find(".html-content"));
		});
	},
	get_edit_html_dialog: function(title, label, $content) {
		var d = new frappe.ui.Dialog({
				title: title,
				fields: [
					{
						fieldname: "content",
						fieldtype: "Text Editor",
						label: label
					},
					{
						fieldname: "help",
						fieldtype: "HTML",
						options: '<p>'
							+ __("You can add dynamic properties from the document by using Jinja templating.")
							+ __("For example: If you want to include the document ID, use {0}", ["<code>{{ doc.name }}</code>"])
						+ '</p>'
					}
				]
			});

		// set existing content in input
		content = $content.html();
		if(content.indexOf("data-no-content")!==-1) content = "";
		d.set_input("content", content);

		d.set_primary_action(__("Update"), function() {
			$content.html(d.get_value("content"));
			d.hide();
		});

		d.show();

		return d;
	},
	save_print_format: function() {
		var data = [],
			me = this;

		// add print heading as the first field
		// this will be removed and set as a doc property
		// before rendering
		data.push({"fieldname": "print_heading_template",
			fieldtype:"HTML",
			options: this.page.main.find(".print-format-builder-print-heading").html()});

		// add pages
		this.page.main.find(".print-format-builder-section").each(function() {
			data.push({"fieldtype": "Section Break"});
			$(this).find(".print-format-builder-column").each(function() {
				data.push({"fieldtype": "Column Break"});
				$(this).find(".print-format-builder-field").each(function() {
					var $this = $(this),
						fieldtype = $this.attr("data-fieldtype"),
						df = {
							fieldname: $this.attr("data-fieldname"),
							print_hide: 0
						};
					if(fieldtype==="Table") {
						// append the user selected columns to visible_columns
						var columns = $this.attr("data-columns").split(",");
						df.visible_columns = [];
						$.each(columns, function(i, c) {
							var parts = c.split("|");
							df.visible_columns.push({
								fieldname:parts[0],
								print_width:parts[1],
								print_hide:0
							});
						});
					}
					if(fieldtype==="Custom HTML") {
						// custom html as HTML field
						df.fieldtype = "HTML";
						df.options = $this.find(".html-content").html();
					}
					data.push(df);
				});
			});
		});

		// save format_data
		frappe.call({
			method: "frappe.client.set_value",
			args: {
				doctype: "Print Format",
				name: this.print_format.name,
				fieldname: "format_data",
				value: JSON.stringify(data),
			},
			callback: function(r) {
				me.print_format = r.message;
				msgprint(__("Saved"));
			}
		});
	}
 });
