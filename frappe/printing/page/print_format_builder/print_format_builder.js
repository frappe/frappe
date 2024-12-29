frappe.pages["print-format-builder"].on_page_load = function (wrapper) {
	frappe.print_format_builder = new frappe.PrintFormatBuilder(wrapper);
	frappe.breadcrumbs.add("Setup", "Print Format");
};

frappe.pages["print-format-builder"].on_page_show = function (wrapper) {
	var route = frappe.get_route();
	if (route.length > 1) {
		frappe.model.with_doc("Print Format", route[1], function () {
			frappe.print_format_builder.print_format = frappe.get_doc("Print Format", route[1]);
			frappe.print_format_builder.refresh();
		});
	} else if (frappe.route_options) {
		if (frappe.route_options.make_new) {
			let { doctype, name, based_on, beta } = frappe.route_options;
			frappe.route_options = null;
			frappe.print_format_builder.setup_new_print_format(doctype, name, based_on, beta);
		} else {
			frappe.print_format_builder.print_format = frappe.route_options.doc;
			frappe.route_options = null;
			frappe.print_format_builder.refresh();
		}
	}
};

frappe.PrintFormatBuilder = class PrintFormatBuilder {
	constructor(parent) {
		this.parent = parent;
		this.make();
		this.refresh();
	}
	refresh() {
		this.custom_html_count = 0;
		if (!this.print_format) {
			this.show_start();
		} else {
			this.page.set_title(this.print_format.name);
			this.setup_print_format();
		}
	}
	make() {
		this.page = frappe.ui.make_app_page({
			parent: this.parent,
			title: __("Print Format Builder"),
		});

		this.page.main.css({ "border-color": "transparent" });

		this.page.sidebar = $('<div class="print-format-builder-sidebar"></div>').appendTo(
			this.page.sidebar
		);
		this.page.main = $('<div class="col-md-12 print-format-builder-main"></div>').appendTo(
			this.page.main
		);

		// future-bindings for buttons on sections / fields
		// bind only once
		this.setup_section_settings();
		this.setup_column_selector();
		this.setup_edit_custom_html();
		// $(this.page.sidebar).css({"position": 'fixed'});
		// $(this.page.main).parent().css({"margin-left": '16.67%'});
	}
	show_start() {
		this.page.main.html(frappe.render_template("print_format_builder_start", {}));
		this.page.clear_actions();
		this.page.set_title(__("Print Format Builder"));
		this.start_edit_print_format();
		this.start_new_print_format();
	}
	start_edit_print_format() {
		// print format control
		var me = this;
		this.print_format_input = frappe.ui.form.make_control({
			parent: this.page.main.find(".print-format-selector"),
			df: {
				fieldtype: "Link",
				options: "Print Format",
				filters: {
					print_format_builder: 1,
				},
				label: __("Select Print Format to Edit"),
				only_select: true,
			},
			render_input: true,
		});

		// create a new print format.
		this.page.main.find(".btn-edit-print-format").on("click", function () {
			var name = me.print_format_input.get_value();
			if (!name) return;
			frappe.model.with_doc("Print Format", name, function (doc) {
				frappe.set_route("print-format-builder", name);
			});
		});
	}
	start_new_print_format() {
		var me = this;
		this.doctype_input = frappe.ui.form.make_control({
			parent: this.page.main.find(".doctype-selector"),
			df: {
				fieldtype: "Link",
				options: "DocType",
				filters: {
					istable: 0,
					issingle: 0,
				},
				label: __("Select a DocType to make a new format"),
			},
			render_input: true,
		});

		this.name_input = frappe.ui.form.make_control({
			parent: this.page.main.find(".name-selector"),
			df: {
				fieldtype: "Data",
				label: __("Name of the new Print Format"),
			},
			render_input: true,
		});

		this.page.main.find(".btn-new-print-format").on("click", function () {
			var doctype = me.doctype_input.get_value(),
				name = me.name_input.get_value();
			if (!(doctype && name)) {
				frappe.msgprint(__("Both DocType and Name required"));
				return;
			}
			me.setup_new_print_format(doctype, name);
		});
	}
	setup_new_print_format(doctype, name, based_on, beta) {
		frappe.call({
			method: "frappe.printing.page.print_format_builder.print_format_builder.create_custom_format",
			args: {
				doctype: doctype,
				name: name,
				based_on: based_on,
				beta: Boolean(beta),
			},
			callback: (r) => {
				if (r.message) {
					let print_format = r.message;
					if (print_format.print_format_builder_beta) {
						frappe.set_route("print-format-builder-beta", print_format.name);
					} else {
						this.print_format = print_format;
						this.refresh();
					}
				}
			},
		});
	}
	setup_print_format() {
		var me = this;
		frappe.model.with_doctype(this.print_format.doc_type, function (doctype) {
			me.meta = frappe.get_meta(me.print_format.doc_type);
			me.setup_sidebar();
			me.render_layout();
			me.page.set_primary_action(__("Save"), function () {
				me.save_print_format();
			});
			me.page.clear_menu();
			me.page.add_menu_item(
				__("Start new Format"),
				function () {
					me.print_format = null;
					me.refresh();
				},
				true
			);
			me.page.clear_inner_toolbar();
			me.page.add_inner_button(__("Edit Properties"), function () {
				frappe.set_route("Form", "Print Format", me.print_format.name);
			});
		});
	}
	setup_sidebar() {
		// prepend custom HTML field
		var fields = [this.get_custom_html_field()].concat(this.meta.fields);
		this.page.sidebar.html(
			$(frappe.render_template("print_format_builder_sidebar", { fields: fields }))
		);
		this.setup_field_filter();
	}
	get_custom_html_field() {
		return {
			fieldtype: "Custom HTML",
			fieldname: "_custom_html",
			label: __("Custom HTML"),
		};
	}
	render_layout() {
		this.page.main.empty();
		this.prepare_data();
		$(
			frappe.render_template("print_format_builder_layout", {
				data: this.layout_data,
				me: this,
			})
		).appendTo(this.page.main);
		this.setup_sortable();
		this.setup_add_section();
		this.setup_edit_heading();
		this.setup_field_settings();
		this.setup_html_data();
	}
	prepare_data() {
		this.print_heading_template = null;
		this.data = JSON.parse(this.print_format.format_data || "[]");
		if (!this.data.length) {
			// new layout
			this.data = this.meta.fields;
		} else {
			// extract print_heading_template if found
			if (this.data[0].fieldname === "print_heading_template") {
				this.print_heading_template = this.data[0].options;
				this.data = this.data.splice(1);
			}
		}

		if (!this.print_heading_template) {
			// default print heading template
			this.print_heading_template =
				'<div class="print-heading">\
				<h2><div>' +
				__(this.print_format.doc_type) +
				'</div><br><small class="sub-heading">{{ _(doc.name) }}</small>\
				</h2></div>';
		}

		this.layout_data = [];
		this.fields_dict = {};
		this.custom_html_dict = {};
		var section = null,
			column = null,
			me = this,
			custom_html_count = 0;

		// create a new placeholder for column and set
		// it as "column"
		var set_column = function () {
			if (!section) set_section();
			column = me.get_new_column();
			section.columns.push(column);
			section.no_of_columns += 1;
		};

		var set_section = function (label) {
			section = me.get_new_section();
			if (label) section.label = label;
			column = null;
			me.layout_data.push(section);
		};

		// break the layout into sections and columns
		// so that it is easier to render in a template
		$.each(this.data, function (i, f) {
			me.fields_dict[f.fieldname] = f;
			if (!f.name && f.fieldname) {
				// from format_data (designed format)
				// print_hide should always be false
				if (f.fieldname === "_custom_html") {
					f.label = "Custom HTML";
					f.fieldtype = "Custom HTML";

					// set custom html id to map data properties later
					custom_html_count++;
					f.custom_html_id = custom_html_count;
					me.custom_html_dict[f.custom_html_id] = f;
				} else {
					f = $.extend(
						frappe.meta.get_docfield(me.print_format.doc_type, f.fieldname) || {},
						f
					);
				}
			}

			if (f.fieldtype === "Section Break") {
				set_section(f.label);
			} else if (f.fieldtype === "Column Break") {
				set_column();
			} else if (!frappe.model.layout_fields.includes(f.fieldtype)) {
				if (!column) set_column();

				if (f.fieldtype === "Table") {
					me.add_table_properties(f);
				}

				if (!f.print_hide) {
					column.fields.push(f);
					section.has_fields = true;
				}
			}
		});

		// strip out empty sections
		this.layout_data = $.map(this.layout_data, function (s) {
			return s.has_fields ? s : null;
		});
	}
	get_new_section() {
		return { columns: [], no_of_columns: 0, label: "" };
	}
	get_new_column() {
		return { fields: [] };
	}
	add_table_properties(f) {
		// build table columns and widths in a dict
		// visible_columns
		var me = this;
		if (!f.visible_columns) {
			me.init_visible_columns(f);
		}
	}
	init_visible_columns(f) {
		f.visible_columns = [];
		$.each(frappe.get_meta(f.options).fields, function (i, _f) {
			if (
				!["Section Break", "Column Break", "Tab Break"].includes(_f.fieldtype) &&
				!_f.print_hide &&
				f.label
			) {
				// column names set as fieldname|width
				f.visible_columns.push({
					fieldname: _f.fieldname,
					print_width: _f.width || "",
					print_hide: 0,
				});
			}
		});
	}
	setup_sortable() {
		var me = this;

		// drag from fields library
		Sortable.create(this.page.sidebar.find(".print-format-builder-sidebar-fields").get(0), {
			group: {
				name: "field",
				put: true,
				pull: "clone",
			},
			sort: false,
			onAdd: function (evt) {
				// on drop, trash!
				$(evt.item).fadeOut();
			},
		});

		// sort, drag and drop between columns
		this.page.main.find(".print-format-builder-column").each(function () {
			me.setup_sortable_for_column(this);
		});

		// section sorting
		Sortable.create(this.page.main.find(".print-format-builder-layout").get(0), {
			handle: ".print-format-builder-section-head",
		});
	}
	setup_sortable_for_column(col) {
		var me = this;
		Sortable.create(col, {
			group: {
				name: "field",
				put: true,
				pull: true,
			},
			onAdd: function (evt) {
				// on drop, change the HTML

				var $item = $(evt.item);
				if (!$item.hasClass("print-format-builder-field")) {
					var fieldname = $item.attr("data-fieldname");

					let field;
					if (fieldname === "_custom_html") {
						field = me.get_custom_html_field();
					} else {
						field = frappe.meta.get_docfield(me.print_format.doc_type, fieldname);
					}

					var html = frappe.render_template("print_format_builder_field", {
						field: field,
						me: me,
					});

					$item.replaceWith(html);
				}
			},
		});
	}
	setup_field_filter() {
		var me = this;
		this.page.sidebar.find(".filter-fields").on("keyup", function () {
			var text = $(this).val();
			me.page.sidebar.find(".field-label").each(function () {
				var show =
					!text || $(this).text().toLowerCase().indexOf(text.toLowerCase()) !== -1;
				$(this).parent().toggle(show);
			});
		});
	}
	setup_section_settings() {
		var me = this;
		this.page.main.on("click", ".section-settings", function () {
			var section = $(this).parent().parent();
			var no_of_columns = section.find(".section-column").length;
			var label = section.attr("data-label");

			// new dialog
			var d = new frappe.ui.Dialog({
				title: "Edit Section",
				fields: [
					{
						label: __("No of Columns"),
						fieldname: "no_of_columns",
						fieldtype: "Select",
						options: ["1", "2", "3", "4"],
					},
					{
						label: __("Section Heading"),
						fieldname: "label",
						fieldtype: "Data",
						description: __("Will only be shown if section headings are enabled"),
					},
					{
						label: __("Remove Section"),
						fieldname: "remove_section",
						fieldtype: "Button",
						click: function () {
							d.hide();
							section.fadeOut(function () {
								section.remove();
							});
						},
						input_class: "btn-danger",
						input_css: {
							"margin-top": "20px",
						},
					},
				],
			});

			d.set_input("no_of_columns", no_of_columns + "");
			d.set_input("label", label || "");

			d.set_primary_action(__("Update"), function () {
				// resize number of columns
				me.update_columns_in_section(
					section,
					no_of_columns,
					cint(d.get_value("no_of_columns"))
				);

				section.attr("data-label", d.get_value("label") || "");
				section.find(".section-label").html(d.get_value("label") || "");

				d.hide();
			});

			d.show();

			return false;
		});
	}
	setup_field_settings() {
		this.page.main.find(".field-settings").on("click", (e) => {
			const field = $(e.currentTarget).parent();
			// new dialog
			var d = new frappe.ui.Dialog({
				title: __("Set Properties"),
				fields: [
					{
						label: __("Label"),
						fieldname: "label",
						fieldtype: "Data",
					},
					{
						label: __("Align Value"),
						fieldname: "align",
						fieldtype: "Select",
						options: [
							{ label: __("Left", null, "alignment"), value: "left" },
							{ label: __("Right", null, "alignment"), value: "right" },
						],
					},
					{
						label: __("Hide Label"),
						fieldname: "nolabel",
						fieldtype: "Check",
					},
					{
						label: __("Remove Field"),
						fieldtype: "Button",
						click: function () {
							d.hide();
							field.remove();
						},
						input_class: "btn-danger",
					},
				],
			});

			d.set_value("label", field.attr("data-label"));
			d.set_value("nolabel", field.attr("data-nolabel"));

			d.set_primary_action(__("Update"), function () {
				field.attr("data-align", d.get_value("align"));
				field.attr("data-label", d.get_value("label"));
				field.attr("data-nolabel", d.get_value("nolabel"));
				field.find(".field-label").html(d.get_value("label"));
				d.hide();
			});

			// set current value
			if (field.attr("data-align")) {
				d.set_value("align", field.attr("data-align"));
			} else {
				d.set_value("align", "left");
			}

			d.show();

			return false;
		});
	}
	setup_html_data() {
		// set JQuery `data` for Custom HTML fields, since editing the HTML
		// directly causes problem becuase of HTML reformatting
		//
		// this is based on a dummy attribute custom_html_id, since all custom html
		// fields have the same fieldname `_custom_html`
		var me = this;
		this.page.main.find('[data-fieldtype="Custom HTML"]').each(function () {
			var fieldname = $(this).attr("data-fieldname");
			var content = $($(this).find(".html-content")[0]);
			var html = me.custom_html_dict[parseInt(content.attr("data-custom-html-id"))].options;
			content.data("content", html);
		});
	}
	update_columns_in_section(section, no_of_columns, new_no_of_columns) {
		var col_size = 12 / new_no_of_columns,
			me = this,
			resize = function () {
				section
					.find(".section-column")
					.removeClass()
					.addClass("section-column")
					.addClass("col-md-" + col_size);
			};

		if (new_no_of_columns < no_of_columns) {
			// move contents of last n columns to previous column
			for (var i = no_of_columns; i > new_no_of_columns; i--) {
				var $col = $(section.find(".print-format-builder-column").get(i - 1));
				var prev = section.find(".print-format-builder-column").get(i - 2);

				// append each field to prev
				$col.parent().addClass("to-drop");
				$col.find(".print-format-builder-field").each(function () {
					$(this).appendTo(prev);
				});
			}

			// drop columns
			section.find(".to-drop").remove();

			// resize
			resize();
		} else if (new_no_of_columns > no_of_columns) {
			// add empty column and resize old columns
			for (let i = no_of_columns; i < new_no_of_columns; i++) {
				var col = $(
					'<div class="section-column">\
					<div class="print-format-builder-column"></div></div>'
				).appendTo(section);
				me.setup_sortable_for_column(col.find(".print-format-builder-column").get(0));
			}
			// resize
			resize();
		}
	}
	setup_add_section() {
		var me = this;
		this.page.main.find(".print-format-builder-add-section").on("click", function () {
			// boostrap new section info
			var section = me.get_new_section();
			section.columns.push(me.get_new_column());
			section.no_of_columns = 1;

			var $section = $(
				frappe.render_template("print_format_builder_section", {
					section: section,
					me: me,
				})
			).appendTo(me.page.main.find(".print-format-builder-layout"));

			me.setup_sortable_for_column($section.find(".print-format-builder-column").get(0));
		});
	}
	setup_edit_heading() {
		var me = this;
		var $heading = this.page.main.find(".print-format-builder-print-heading");

		// set content property
		$heading.data("content", this.print_heading_template);

		this.page.main.find(".edit-heading").on("click", function () {
			var d = me.get_edit_html_dialog(__("Edit Heading"), __("Heading"), $heading);
		});
	}
	setup_column_selector() {
		var me = this;
		this.page.main.on("click", ".select-columns", function () {
			var parent = $(this).parents(".print-format-builder-field:first"),
				doctype = parent.attr("data-doctype"),
				label = parent.attr("data-label"),
				nolabel = parent.attr("data-nolabel"),
				columns = parent.attr("data-columns").split(","),
				column_names = $.map(columns, function (v) {
					return v.split("|")[0];
				}),
				widths = {};

			$.each(columns, function (i, v) {
				var parts = v.split("|");
				widths[parts[0]] = parts[1] || "";
			});

			var d = new frappe.ui.Dialog({
				title: __("Select Table Columns for {0}", [label]),
			});

			var $body = $(d.body);

			var doc_fields = frappe.get_meta(doctype).fields;
			var docfields_by_name = {};

			// docfields by fieldname
			$.each(doc_fields, function (j, f) {
				if (f) docfields_by_name[f.fieldname] = f;
			});

			// add field which are in column_names first to preserve order
			var fields = [];
			$.each(column_names, function (i, v) {
				if (Object.keys(docfields_by_name).includes(v)) {
					fields.push(docfields_by_name[v]);
				}
			});
			// add remaining fields
			$.each(doc_fields, function (j, f) {
				if (
					f &&
					!column_names.includes(f.fieldname) &&
					!["Section Break", "Column Break", "Tab Break"].includes(f.fieldtype) &&
					f.label
				) {
					fields.push(f);
				}
			});
			// render checkboxes
			$(
				frappe.render_template("print_format_builder_column_selector", {
					fields: fields,
					column_names: column_names,
					widths: widths,
				})
			).appendTo(d.body);

			Sortable.create($body.find(".column-selector-list").get(0));

			var get_width_input = function (fieldname) {
				return $body.find(".column-width[data-fieldname='" + fieldname + "']");
			};

			// update data-columns property on update
			d.set_primary_action(__("Update"), function () {
				var visible_columns = [];
				$body.find("input:checked").each(function () {
					var fieldname = $(this).attr("data-fieldname"),
						width = get_width_input(fieldname).val() || "";
					visible_columns.push(fieldname + "|" + width);
				});
				parent.attr("data-columns", visible_columns.join(","));
				d.hide();
			});

			let update_column_count_message = () => {
				// show a warning if user selects more than 10 columns for a table
				let columns_count = $body.find("input:checked").length;
				$body.find(".help-message").toggle(columns_count > 10);
			};
			update_column_count_message();

			// enable / disable input based on selection
			$body.on("click", "input[type='checkbox']", function () {
				var disabled = !$(this).prop("checked"),
					input = get_width_input($(this).attr("data-fieldname"));

				input.prop("disabled", disabled);
				if (disabled) input.val("");

				update_column_count_message();
			});

			d.show();

			return false;
		});
	}
	get_visible_columns_string(f) {
		if (!f.visible_columns) {
			this.init_visible_columns(f);
		}
		return $.map(f.visible_columns, function (v) {
			return v.fieldname + "|" + (v.print_width || "");
		}).join(",");
	}
	get_no_content() {
		return __("Edit to add content");
	}
	setup_edit_custom_html() {
		var me = this;
		this.page.main.on("click", ".edit-html", function () {
			me.get_edit_html_dialog(
				__("Edit Custom HTML"),
				__("Custom HTML"),
				$(this).parents(".print-format-builder-field:first").find(".html-content")
			);
		});
	}
	get_edit_html_dialog(title, label, $content) {
		var me = this;
		var d = new frappe.ui.Dialog({
			title: title,
			fields: [
				{
					fieldname: "content",
					fieldtype: "Code",
					label: label,
					options: "HTML",
				},
				{
					fieldname: "help",
					fieldtype: "HTML",
					options:
						"<p>" +
						__(
							"You can add dynamic properties from the document by using Jinja templating."
						) +
						__("For example: If you want to include the document ID, use {0}", [
							"<code>{{ doc.name }}</code>",
						]) +
						"</p>",
				},
			],
		});

		// set existing content in input
		var content = $content.data("content") || "";
		if (content.indexOf(me.get_no_content()) !== -1) content = "";
		d.set_input("content", content);

		d.set_primary_action(__("Update"), function () {
			$($content[0]).data("content", d.get_value("content"));
			$content.html(d.get_value("content"));
			d.hide();
		});

		d.show();

		return d;
	}
	save_print_format() {
		var data = [],
			me = this;

		// add print heading as the first field
		// this will be removed and set as a doc property
		// before rendering
		data.push({
			fieldname: "print_heading_template",
			fieldtype: "Custom HTML",
			options: this.page.main.find(".print-format-builder-print-heading").data("content"),
		});

		// add pages
		this.page.main.find(".print-format-builder-section").each(function () {
			var section = { fieldtype: "Section Break", label: $(this).attr("data-label") || "" };
			data.push(section);
			$(this)
				.find(".print-format-builder-column")
				.each(function () {
					data.push({ fieldtype: "Column Break" });
					$(this)
						.find(".print-format-builder-field")
						.each(function () {
							var $this = $(this),
								fieldtype = $this.attr("data-fieldtype"),
								align = $this.attr("data-align"),
								label = $this.attr("data-label"),
								nolabel = $this.attr("data-nolabel"),
								df = {
									fieldname: $this.attr("data-fieldname"),
									print_hide: 0,
								};

							if (align) {
								df.align = align;
							}

							if (label) {
								df.label = label;
							}

							if (cint(nolabel)) {
								df.nolabel = 1;
							}

							if (fieldtype === "Table") {
								// append the user selected columns to visible_columns
								var columns = $this.attr("data-columns").split(",");
								df.visible_columns = [];
								$.each(columns, function (i, c) {
									var parts = c.split("|");
									df.visible_columns.push({
										fieldname: parts[0],
										print_width: parts[1],
										print_hide: 0,
									});
								});
							}
							if (fieldtype === "Custom HTML") {
								// custom html as HTML field
								df.fieldtype = "HTML";
								df.options = $($this.find(".html-content")[0]).data("content");
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
			freeze: true,
			btn: this.page.btn_primary,
			callback: function (r) {
				me.print_format = r.message;
				locals["Print Format"][me.print_format.name] = r.message;
				frappe.show_alert({ message: __("Saved"), indicator: "green" });
			},
		});
	}
};
