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
			data: this.layout_data
		})).appendTo(this.page.main);
		this.setup_sortable();
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
			column = {fields: []};
			section.columns.push(column);
			section.no_of_columns += 1;
		}

		// break the layout into sections and columns
		// so that it is easier to render in a template
		$.each(this.data, function(i, f) {
			if(f.fieldtype==="Section Break") {
				section = {columns: [], no_of_columns: 0};
				column = null;
				me.layout_data.push(section);

			} else if(f.fieldtype==="Column Break") {
				set_column();

			} else if(!in_list(["Section Break", "Column Break", "Fold"], f.fieldtype)
				&& !f.print_hide) {
				if(!column) set_column();

				column.fields.push(f);
				section.has_fields = true;
			}
		});

		// strip out empty sections
		this.layout_data = $.map(this.layout_data, function(s) {
			return s.has_fields ? s : null
		});
	},
	setup_sortable: function() {
		Sortable.create(this.page.sidebar.find(".print-format-builder-fields").get(0),
			{
				group: {put: false, pull:"clone"},
				sort: false
			});

		this.page.main.find(".print-format-builder-column").each(function() {
			Sortable.create(this, {
				group: {
					put: true,
					pull: true
				}
			});
		})
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
	}
 });

frappe.PrintFormatField = Class.extend({
	init: function() { }
});
