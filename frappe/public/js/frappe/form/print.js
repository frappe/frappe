frappe.provide("frappe.ui.form");

frappe.ui.form.PrintPreview = Class.extend({
	init: function (opts) {
		$.extend(this, opts);
		this.make();
		this.bind_events();
	},
	make: function () {
		this.wrapper = this.frm.page.add_view("print", frappe.render_template("print_layout", {}));

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

		this.print_formats = frappe.meta.get_print_formats(this.frm.meta.name);
		this.print_letterhead = this.wrapper
			.find(".print-letterhead")
			.on("change", function () { me.print_sel.trigger("change"); })
			.prop("checked", cint(
				(frappe.model.get_doc(":Print Settings", "Print Settings")
					|| { with_letterhead: 1 }).with_letterhead) ? true : false);
		this.print_sel = this.wrapper
			.find(".print-preview-select")
			.on("change", function () {
				me.set_default_print_language();
				me.multilingual_preview();
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
			}
		});

		this.wrapper.find(".btn-print-edit").on("click", function () {
			let print_format = me.get_print_format();
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
	set_user_lang: function () {
		this.lang_code = this.frm.doc.language;
		// Load all languages in the field
		this.language_sel.empty()
			.add_options([{value:'', label:__("Select Language...")}]
				.concat(frappe.get_languages()))
			.val(this.lang_code);
		this.preview();
	},
	set_default_print_language: function () {
 		var print_format = this.get_print_format();

 		if (print_format.default_print_language) {
 			this.lang_code = print_format.default_print_language;
 			this.language_sel.val(this.lang_code);
 		} else {
			this.language_sel.val(frappe.boot.lang);
		}
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
		this.get_print_html(function (out) {
			me.wrapper.find(".print-format").html(out.html);
			me.show_footer();
			me.set_style(out.style);
		});
	},
	show_footer: function() {
		// footer is hidden by default as reqd by pdf generation
		// simple hack to show it in print preview
		this.wrapper.find('.page-break').css({
			'display': 'flex',
			'flex-direction': 'column'
		});
		this.wrapper.find('#footer-html').attr('style', `
			display: block !important;
			order: 1;
			margin-top: 20px;
		`);
	},
	printit: function () {
		let print_server ;
		var me = this;
		frappe.call({
			method: "frappe.printing.doctype.print_settings.print_settings.is_print_server_enabled",
			callback: function (data) {
				if (data.message) {
					frappe.call({
						"method": "frappe.utils.print_format.print_by_server",
						args: {
							doctype: me.frm.doc.doctype,
							name: me.frm.doc.name,
							print_format:  me.selected_format(),
							no_letterhead: me.with_letterhead()
						},
						callback: function (data) {
						}
					});
				} else {
					me.new_page_preview(true);
				}
			}
		});
	},
	new_page_preview: function (printit) {
		var me = this;
		var w = window.open(frappe.urllib.get_full_url("/printview?"
			+ "doctype=" + encodeURIComponent(me.frm.doc.doctype)
			+ "&name=" + encodeURIComponent(me.frm.doc.name)
			+ (printit ? "&trigger_print=1" : "")
			+ "&format=" + me.selected_format()
			+ "&no_letterhead=" + (me.with_letterhead() ? "0" : "1")
			+ (me.lang_code ? ("&_lang=" + me.lang_code) : "")));
		if (!w) {
			frappe.msgprint(__("Please enable pop-ups")); return;
		}
	},
	get_print_html: function (callback) {
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
		this.print_formats = frappe.meta.get_print_formats(this.frm.doctype);
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
	}, {
		fieldtype: "Select",
		fieldname: "orientation",
		label: __("Orientation"),
		options: "Landscape\nPortrait",
		default: "Landscape"
	}];

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
