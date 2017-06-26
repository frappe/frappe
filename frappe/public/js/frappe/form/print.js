frappe.provide("frappe.ui.form");

frappe.ui.form.PrintPreview = Class.extend({
	init: function (opts) {
		$.extend(this, opts);
		this.type = this.frm ? "DocType" : "Report";
		this.page = this.frm ? this.frm.page : this.report.page;
		this.make();
		this.bind_events();
	},
	make: function () {
		this.wrapper = this.page.add_view("print", frappe.render_template("print_layout", {}));

		// only system manager can edit
		this.wrapper.find(".btn-print-edit").toggle(frappe.user.has_role("System Manager"));
	},
	bind_events: function () {
		var me = this;
		this.wrapper.find(".btn-print-close").click(function () {
			me.frm.hide_print();
		});

		// hide print view on pressing escape, only if there is no focus on any input
		$(document).on("keydown", function (e) {
			if (e.which === 27 && me.frm && e.target === document.body) {
				me.frm.hide_print();
			}
		});

		this.update_print_formats();
		this.print_letterhead = this.wrapper
			.find(".print-letterhead")
			.on("change", function () { me.print_sel.trigger("change"); })
			.prop("checked", cint(
				(frappe.model.get_doc(":Print Settings", "Print Settings")
					|| { with_letterhead: 1 }).with_letterhead) ? true : false);
		this.print_sel = this.wrapper
			.find(".print-preview-select")
			.on("change", function () {
				me.multilingual_preview()
			});

		//On selection of language get code and pass it to preview method
		this.language_sel = this.wrapper
			.find(".languages")
			.on("change", function () {
				me.lang_code = me.language_sel.val()
				me.multilingual_preview()
			});

		this.wrapper.find(".btn-print-print").click(function () {
			if (me.is_old_style()) {
				me.print_old_style();
			} else {
				me.printit();
			}
		});

		this.wrapper.find(".btn-print-preview").click(function () {
			if (me.is_old_style()) {
				me.new_page_preview_old_style();
			} else {
				me.new_page_preview();
			}
		});

		this.wrapper.find(".btn-download-pdf").click(function () {
			if (!me.is_old_style()) {
				if (this.type == "DocType") {
					var w = window.open(
						frappe.urllib.get_full_url("/api/method/frappe.utils.print_format.download_pdf?"
							+ "doctype=" + encodeURIComponent(me.frm.doc.doctype)
							+ "&name=" + encodeURIComponent(me.frm.doc.name)
							+ "&format=" + me.selected_format()
							+ "&no_letterhead=" + (me.with_letterhead() ? "0" : "1")
							+ (me.lang_code ? ("&_lang=" + me.lang_code) : ""))
					);
					if (!w) {
						frappe.msgprint(__("Please enable pop-ups")); return;
					}
				} else {
					me.report.open_pdf_report(me.get_print_template_html(), me.print_settings.landscape ? "Landscape" : "Portrait");
				}
			}
		});

		this.wrapper.find(".btn-print-edit").on("click", function () {
			var print_format = me.get_print_format();
			if (print_format && print_format.name) {
				if (print_format.print_format_builder) {
					frappe.set_route("print-format-builder", print_format.name);
				} else {
					frappe.set_route("Form", "Print Format", print_format.name);
				}
			} else {
				// start a new print format
				frappe.prompt({
					fieldname: "print_format_name", fieldtype: "Data", reqd: 1,
					label: "New Print Format Name"
				}, function (data) {
					frappe.route_options = {
						make_new: true,
						doctype: me.frm.doctype,
						name: data.print_format_name
					};
					frappe.set_route("print-format-builder");
				}, __("New Custom Print Format"), __("Start"));
			}
		});
	},
	update_print_formats: function() {
		this.print_formats = frappe.meta.get_print_formats(this.type == "DocType" ? this.frm.meta.name : this.report.report_name, this.type);
	},
	set_user_lang: function () {
		this.lang_code = this.frm.doc.language;
		// Load all languages in the field
		this.language_sel.empty()
			.add_options(frappe.get_languages())
			.val(this.lang_code);
		this.preview();
	},
	multilingual_preview: function () {
		var me = this;
		if (this.is_old_style()) {
			me.wrapper.find(".btn-download-pdf").toggle(false);
			me.set_style();
			me.preview_old_style();
		} else {
			me.wrapper.find(".btn-download-pdf").toggle(true);
			me.preview();
		}
	},
	preview: function () {
		var me = this;
		this.get_preview_html(function (out) {
			me.wrapper.find(".print-format").html(out.html);
			me.set_style(out.style);
		});
	},
	printit: function () {
		this.new_page_preview(true);
	},
	new_page_preview: function (printit) {
		if (this.type == "DocType") {
			var me = this;
			var w = window.open(frappe.urllib.get_full_url("/printview?"
				+ (printit ? "trigger_print=1" : "")
				+ "&doctype=" + encodeURIComponent(me.frm.doc.doctype)
				+ "&name=" + encodeURIComponent(me.frm.doc.name)
				+ "&no_letterhead=" + (me.with_letterhead() ? "0" : "1")
				+ "&format=" + me.selected_format()
				+ (me.lang_code ? ("&_lang=" + me.lang_code) : "")));
			if (!w) {
				frappe.msgprint(__("Please enable pop-ups")); return;
			}
		} else {
			// logic from microtemplate.js render_grid()
			// not using frappe.render_grid() from microtemplate
			// to reuse the print-preview already shown
			var html = this.get_print_template_html();

			var wnd = window.open();
			if(!wnd) {
				frappe.msgprint(__("Please enable pop-ups in your browser"));
				return;
			}
			wnd.document.write(html);
			wnd.document.close();

			if (printit) {
				// trigger print script
				var elements = wnd.document.getElementsByTagName("tr");
				var i = elements.length;
				while (i--) {
					if(elements[i].clientHeight>300){
						elements[i].setAttribute("style", "page-break-inside: auto;");
					}
				}

				setTimeout(function() {
					wnd.focus();
					wnd.print();
					wnd.close();
				}, 500);
			}
		}
	},
	get_preview_html: function (callback) {
		if (this.type == "DocType") {
			frappe.call({
				method: "frappe.www.printview.get_html_and_style",
				args: {
					doc: this.frm.doc,
					print_format: this.selected_format(),
					no_letterhead: !this.with_letterhead() ? 1 : 0,
					_lang: this.lang_code
				},
				callback: function (r) {
					if (!r.exc) {
						callback(r.message);
					}
				}
			});
		} else {
			// Client side print
			this.print_css = frappe.boot.print_css;
			var selected_format = this.selected_format();

			var columns = this.report.grid.getColumns();

			this.print_settings = locals[":Print Settings"]["Print Settings"];
			this.print_settings.with_letter_head = this.with_letterhead();
			this.print_settings.landscape = this.report.html_format ? false : columns.length > 10; // microtemplate.js #110
			if (!this.print_settings.with_letter_head)
				this.print_settings.letter_head = null;


			if (selected_format === "Standard" && !this.report.html_format) {
				// rows filtered by inline_filter of slickgrid
				var visible_idx = frappe.slickgrid_tools
					.get_view_data(this.report.columns, this.report.dataView)
					.map(row => row[0]).filter(idx => idx !== 'Sr No');

				var data = this.report.grid.getData().getItems();
				data = data.filter(d => visible_idx.includes(d._id));
				var content = frappe.render_template("print_grid", {
					title:__(this.report.report_name),
					data:data,
					columns:columns
				});
			} else {
				var html_format = this.report.html_format;
				if (selected_format != "Standard") {
					var format = this.get_print_format(selected_format);
					html_format = format && format.html;
					this.print_css += format && format.css;
				}
				content = frappe.render(html_format, {
					data: frappe.slickgrid_tools.get_filtered_items(this.report.dataView),
					filters:this.report.get_values(),
					report:this.report
				});
			}
			callback({html: content, style: this.print_css});
		}
	},
	get_print_template_html: function() {
		var base_url = frappe.urllib.get_base_url();
		return frappe.render_template("print_template",{
			content:this.wrapper.find(".print-format").html(),
			title:__(this.report.report_name),
			base_url: base_url,
			print_css: this.print_css,
			print_settings: this.print_settings,
			landscape: this.print_settings.landscape,
			columns: this.report.grid.getColumns()
		});
	},
	preview_old_style: function () {
		var me = this;
		this.with_old_style({
			format: me.print_sel.val(),
			callback: function (html) {
				me.wrapper.find(".print-format").html('<div class="alert alert-warning">'
					+ __("Warning: This Print Format is in old style and cannot be generated via the API.")
					+ '</div>'
					+ html);
			},
			no_letterhead: !this.with_letterhead(),
			only_body: true,
			no_heading: true
		});
	},
	refresh_print_options: function () {
		this.update_print_formats();
		return this.print_sel
			.empty().add_options(this.print_formats);
	},
	with_old_style: function (opts) {
		frappe.require("/assets/js/print_format_v3.min.js", function () {
			_p.build(opts.format, opts.callback, opts.no_letterhead, opts.only_body, opts.no_heading);
		});
	},
	print_old_style: function () {
		var me = this;
		frappe.require("/assets/js/print_format_v3.min.js", function () {
			_p.build(me.print_sel.val(), _p.go,
				!me.with_letterhead());
		});
	},
	new_page_preview_old_style: function () {
		var me = this;
		frappe.require("/assets/js/print_format_v3.min.js", function () {
			_p.build(me.print_sel.val(), _p.preview, !me.with_letterhead());
		});
	},
	selected_format: function () {
		return this.print_sel.val() || this.frm.meta.default_print_format || "Standard";
	},
	is_old_style: function (format) {
		return this.get_print_format(format).print_format_type === "Client";
	},
	get_print_format: function (format) {
		if (!format) {
			format = this.selected_format();
		}

		if (locals["Print Format"] && locals["Print Format"][format]) {
			return locals["Print Format"][format]
		} else {
			return {}
		}
	},
	with_letterhead: function () {
		return this.print_letterhead.is(":checked") ? 1 : 0;
	},
	set_style: function (style) {
		frappe.dom.set_style(style || frappe.boot.print_css, "print-style");
	}
});

frappe.ui.get_print_settings = function (pdf, callback, letter_head) {
	var print_settings = locals[":Print Settings"]["Print Settings"];

	var default_letter_head = locals[":Company"] && frappe.defaults.get_default('company')
		? locals[":Company"][frappe.defaults.get_default('company')]["default_letter_head"]
		: '';

	var columns = [{
		fieldtype: "Check",
		fieldname: "with_letter_head",
		label: __("With Letter head")
	}, {
		fieldtype: "Select",
		fieldname: "letter_head",
		label: __("Letter Head"),
		depends_on: "with_letter_head",
		options: $.map(frappe.boot.letter_heads, function (i, d) { return d }),
		default: letter_head || default_letter_head
	}];

	if (pdf) {
		columns.push({
			fieldtype: "Select",
			fieldname: "orientation",
			label: __("Orientation"),
			options: "Landscape\nPortrait",
			default: "Landscape"
		})
	}

	frappe.prompt(columns, function (data) {
		var data = $.extend(print_settings, data);
		if (!data.with_letter_head) {
			data.letter_head = null;
		}
		if (data.letter_head) {
			data.letter_head = frappe.boot.letter_heads[print_settings.letter_head];
		}
		callback(data);
	}, __("Print Settings"));
}
