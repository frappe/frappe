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
		this.new_page_preview(true);
	},
	new_page_preview: function (printit) {
		var me = this;
		if (me.frm.doctype == 'Sales Invoice' || me.frm.doctype == 'Payment Entry' ){
                var datalist = '';
                if (me.frm.doctype == 'Sales Invoice'){
                    datalist = {"self.base_net_total": me.frm.doc.base_net_total, "self.contact_email":me.frm.doc.contact_email , "self.customer_address": me.frm.doc.customer_address,
                             "self.territory": me.frm.doc.territory, "self.company_currency": me.frm.doc.currency, "self.net_total": me.frm.doc.net_total,
                             "self.account_for_change_amount": me.frm.doc.account_for_change_amount, "self.base_paid_amount": me.frm.doc.base_paid_amount,
                             "self.name": me.frm.doc.name, "self.company_address": me.frm.doc.company_address,
                             "self.status": me.frm.doc.status, "self.debit_to": me.frm.doc.debit_to, "self.base_rounded_total": me.frm.doc.base_rounded_total,
                             "self.contact_mobile": me.frm.doc.contact_mobile, "self.grand_total": me.frm.doc.grand_total, "self.posting_date": me.frm.doc.posting_date,
                             "self.discount_amount": me.frm.doc.discount_amount, "self.paid_amount": me.frm.doc.paid_amount,
                              "self.in_words": me.frm.doc.in_words, "self.total_taxes_and_charges": me.frm.doc.total_taxes_and_charges,
                              "self.against_income_account": me.frm.doc.against_income_account, "self.posting_time": me.frm.doc.posting_time, "self.company": me.frm.doc.company,
                              "self.base_grand_total":me.frm.doc.base_grand_total, "self.base_in_words": me.frm.doc.base_in_words, "self.customer": me.frm.doc.customer}
                }
                else{
                    datalist = {"self.received_amount": me.frm.doc.received_amount, "self.payment_type": me.frm.doc.payment_type,
                    "self.difference_amount": me.frm.doc.difference_amount, "self.company_currency": me.frm.doc.paid_from_account_currency,
                     "self.total_allocated_amount": me.frm.doc.total_allocated_amount, "self.paid_to": me.frm.doc.paid_to, "self.doctype": me.frm.doc.doctype,
                     "self.base_paid_amount": me.frm.doc.base_paid_amount,"self.name": me.frm.doc.name, "self.party_type": me.frm.doc.party_type,
                     "self.creation": me.frm.doc.creation, "self.base_total_allocated_amount": me.frm.doc.base_total_allocated_amount,
                     "self.base_received_amount": me.frm.doc.base_received_amount, "self.party_account": me.frm.doc.party_account,
                     "self.allocate_payment_amount": me.frm.doc.allocate_payment_amount, "self.party_name": me.frm.doc.party_name,
                     "self.remarks": me.frm.doc.remarks, "self.posting_date": me.frm.doc.posting_date,
                     "self.paid_to_account_balance": me.frm.doc.paid_to_account_balance, "self.amended_from": me.frm.doc.amended_from,
                     "self.paid_amount": me.frm.doc.paid_amount, "self.modified": me.frm.doc.modified,
                     "self.company": me.frm.doc.company, "self.modified_by": me.frm.doc.modified_by, "self.paid_from_account_currency": me.frm.doc.paid_from_account_currency,
                     "self.party_balance": me.frm.doc.party_balance, "self.mode_of_payment": me.frm.doc.mode_of_payment, "self.paid_to_account_currency": me.frm.doc.paid_to_account_currency,
                     "self.owner": me.frm.doc.owner, "self.paid_from_account_balance": me.frm.doc.paid_from_account_balance, "self.party": me.frm.doc.party}
                }
                var a = frappe.call({
                     method: "frappe.core.doctype.transactionlog.transactionlog.create_transaction_log",
                     args: {
                      doctype: me.frm.doctype,
                      document: me.frm.docname,
                      data: datalist
                           }
                       });
               }
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
