

frappe.ui.form.PrintPreview = Class.extend({
	init: function (opts) {
		$.extend(this, opts);
		this.make();
		this.bind_events();
		this.setup_keyboard_shortcuts();
	},
	make: function () {
		this.wrapper = this.frm.page.add_view("print", frappe.render_template("print_layout", {}));

		// only system manager can edit
		this.wrapper.find(".btn-print-edit").toggle(frappe.user.has_role("System Manager"));
		if (frappe.model.get_doc(":Print Settings", "Print Settings").enable_raw_printing == "1") {
			this.wrapper.find(".btn-printer-setting").toggle(true);
		}
	},
	bind_events: function () {
		var me = this;
		this.wrapper.find(".btn-print-close").click(function () {
			me.hide();
		});

		// hide print view on pressing escape, only if there is no focus on any input
		$(document).on("keydown", function (e) {
			if (e.which === 27 && me.frm && e.target === document.body) {
				me.hide();
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

		this.wrapper.find(".btn-printer-setting").click(function () {
			me.printer_setting_dialog();
		});

		this.wrapper.find(".btn-print-print").click(function () {
			me.printit();
		});

		this.wrapper.find(".btn-print-preview").click(function () {
			me.new_page_preview();
		});

		this.wrapper.find(".btn-download-pdf").click(function () {
			var w = window.open(
				frappe.urllib.get_full_url("/api/method/frappe.utils.print_format.download_pdf?"
					+ "doctype=" + encodeURIComponent(me.frm.doc.doctype)
					+ "&name=" + encodeURIComponent(me.frm.doc.name)
					+ "&format=" + encodeURIComponent(me.selected_format())
					+ "&no_letterhead=" + (me.with_letterhead() ? "0" : "1")
					+ (me.lang_code ? ("&_lang=" + me.lang_code) : ""))
			);
			if (!w) {
				frappe.msgprint(__("Please enable pop-ups")); return;
			}
		});

		this.wrapper.find(".btn-print-edit").on("click", function () {
			let print_format = me.get_print_format();
			let is_custom_format = print_format.name
				&& print_format.print_format_builder
				&& print_format.standard === 'No';
			let is_standard_but_editable = print_format.name && print_format.custom_format;

			if (is_standard_but_editable) {
				frappe.set_route("Form", "Print Format", print_format.name);
				return;
			}
			if (is_custom_format) {
				frappe.set_route("print-format-builder", print_format.name);
				return;
			}
			// start a new print format
			frappe.prompt([
				{
					label: __("New Print Format Name"),
					fieldname: "print_format_name",
					fieldtype: "Data",
					reqd: 1,
				},
				{
					label: __('Based On'),
					fieldname: 'based_on',
					fieldtype: 'Read Only',
					default: print_format.name || 'Standard'
				}
			], (data) => {
				frappe.route_options = {
					make_new: true,
					doctype: me.frm.doctype,
					name: data.print_format_name,
					based_on: data.based_on
				};
				frappe.set_route("print-format-builder");
			}, __("New Custom Print Format"), __("Start"));
		});

		$(document).on('new-print-format', (e) => {
			this.refresh_print_options();
			if (e.print_format) {
				this.print_sel.val(e.print_format);
			}
			// start a new print format
			frappe.prompt([
				{
					label: __("New Print Format Name"),
					fieldname: "print_format_name",
					fieldtype: "Data",
					reqd: 1,
				},
				{
					label: __('Based On'),
					fieldname: 'based_on',
					fieldtype: 'Read Only',
					default: print_format.name || 'Standard'
				}
			], function (data) {
				frappe.route_options = {
					make_new: true,
					doctype: me.frm.doctype,
					name: data.print_format_name,
					based_on: data.based_on
				};
				frappe.set_route("print-format-builder");
			}, __("New Custom Print Format"), __("Start"));
		});
	},
	setup_keyboard_shortcuts() {
		this.wrapper.find('.print-toolbar a.btn-default').each((i, el) => {
			frappe.ui.keys.get_shortcut_group(this.frm.page).add($(el));
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
		this.lang_code = print_format.default_print_language || this.frm.doc.language || frappe.boot.lang;
		this.language_sel.val(this.lang_code);
 	},
	multilingual_preview: function () {
		var me = this;
		if (this.is_raw_printing()) {
			me.wrapper.find(".btn-print-preview").toggle(false);
			me.wrapper.find(".btn-download-pdf").toggle(false);
			me.preview();
		} else {
			me.wrapper.find(".btn-print-preview").toggle(true);
			me.wrapper.find(".btn-download-pdf").toggle(true);
			me.preview();
		}
	},
	toggle: function() {
		if(this.wrapper.is(":visible")) {
			// hide
			this.hide();
			return;
		} else {
			// show
			if(!frappe.model.can_print(this.frm.doc.doctype, this.frm)) {
				frappe.msgprint(__("You are not allowed to print this document"));
				return;
			}
			this.refresh_print_options().trigger("change");
			this.frm.page.set_view("print");
			this.set_user_lang();
			this.set_default_print_language();
			this.preview();
		}
	},
	preview: function () {
		var me = this;
		this.get_print_html(out => {
			if (!out.html) {
				out.html = this.get_no_preview_html();
			}
			const $print_format = me.wrapper.find(".print-format");
			$print_format.html(out.html);
			me.show_footer();
			me.set_style(out.style);

			const print_height = $print_format.get(0).offsetHeight;
			const $message = me.wrapper.find(".page-break-message");

			const print_height_inches = frappe.dom.pixel_to_inches(print_height);
			// if contents are large enough, indicate that it will get printed on multiple pages
			// Maximum height for an A4 document is 11.69 inches
			if (print_height_inches > 11.69) {
				$message.text(__('This may get printed on multiple pages'));
			} else {
				$message.text('');
			}
		});
	},
	hide: function() {
		if(this.frm.setup_done && this.frm.page.current_view_name==="print") {
			this.frm.page.set_view(this.frm.page.previous_view_name==="print" ?
				"main" : (this.frm.page.previous_view_name || "main"));
		}
	},
	show_footer: function() {
		// footer is hidden by default as reqd by pdf generation
		// simple hack to show it in print preview
		this.wrapper.find('.print-format').css({
			display: 'flex',
			flexDirection: 'column'
		});
		this.wrapper.find('.page-break').css({
			'display': 'flex',
			'flex-direction': 'column',
			'flex': '1'
		});
		this.wrapper.find('#footer-html').attr('style', `
			display: block !important;
			order: 1;
			margin-top: auto;
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
				} else if (me.get_mapped_printer().length === 1) {
					// printer is already mapped in localstorage (applies for both raw and pdf )
					if (me.is_raw_printing()) {
						me.get_raw_commands(function (out) {
							frappe.ui.form.qz_connect().then(function () {
								let printer_map = me.get_mapped_printer()[0];
								let data = [out.raw_commands];
								let config = qz.configs.create(printer_map.printer);
								return qz.print(config, data);
							}).then(frappe.ui.form.qz_success).catch((err) => {
								frappe.ui.form.qz_fail(err);
							});
						});
					} else {
						frappe.show_alert({
							message: __('PDF printing via "Raw Print" is not yet supported. Please remove the printer mapping in Printer Settings and try again.'),
							indicator: 'blue'
						}, 14);
						//Note: need to solve "Error: Cannot parse (FILE)<URL> as a PDF file" to enable qz pdf printing.
					}
				} else if (me.is_raw_printing()) {
					// printer not mapped in localstorage and the current print format is raw printing
					frappe.show_alert({
						message: __('Please set a printer mapping for this print format in the Printer Settings'),
						indicator: 'blue'
					}, 14);
					me.printer_setting_dialog();
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
			+ "&format=" + encodeURIComponent(me.selected_format())
			+ "&no_letterhead=" + (me.with_letterhead() ? "0" : "1")
			+ (me.lang_code ? ("&_lang=" + me.lang_code) : "")));
		if (!w) {
			frappe.msgprint(__("Please enable pop-ups")); return;
		}
	},
	get_print_html: function (callback) {
		let print_format = this.get_print_format();
		if (print_format.raw_printing) {
			callback({
				html: this.get_no_preview_html()
			});
			return;
		}
		if (this._req) {
			this._req.abort();
		}
		this._req = frappe.call({
			method: "frappe.www.printview.get_html_and_style",
			args: {
				doc: this.frm.doc,
				print_format: this.selected_format(),
				no_letterhead: !this.with_letterhead() ? 1 : 0,
				_lang: this.lang_code,
			},
			callback: function (r) {
				if (!r.exc) {
					callback(r.message);
				}
			}
		});
	},
	get_no_preview_html() {
		return `<div class="text-muted text-center" style="font-size: 1.2em;">
			${__("No Preview Available")}
		</div>` ;
	},
	get_raw_commands: function (callback) {
		// fetches rendered raw commands from the server for the current print format.
		frappe.call({
			method: "frappe.www.printview.get_rendered_raw_commands",
			args: {
				doc: this.frm.doc,
				print_format: this.selected_format(),
				_lang: this.lang_code
			},
			callback: function (r) {
				if (!r.exc) {
					callback(r.message);
				}
			}
		});
	},
	get_mapped_printer: function () {
		// returns a list of "print format: printer" mapping filtered by the current print format
		let print_format_printer_map = this.get_print_format_printer_map();
		if (print_format_printer_map[this.frm.doctype]) {
			return print_format_printer_map[this.frm.doctype].filter(
				(printer_map) => printer_map.print_format == this.selected_format());
		} else {
			return [];
		}
	},
	get_print_format_printer_map: function () {
		// returns the whole object "print_format_printer_map" stored in the localStorage.
		try {
			let print_format_printer_map = JSON.parse(localStorage.print_format_printer_map);
			return print_format_printer_map;
		} catch (e) {
			return {};
		}
	},
	refresh_print_options: function () {
		this.print_formats = frappe.meta.get_print_formats(this.frm.doctype);
		return this.print_sel
			.empty().add_options(this.print_formats);

	},
	selected_format: function () {
		return this.print_sel.val() || this.frm.meta.default_print_format || "Standard";
	},
	is_raw_printing: function (format) {
		return this.get_print_format(format).raw_printing === 1;
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
	},
	printer_setting_dialog: function () {
		// dialog for the Printer Settings
		var me = this;
		this.print_format_printer_map = me.get_print_format_printer_map();
		this.data = [];
		this.data = this.print_format_printer_map[this.frm.doctype] || [];
		this.printer_list = [];
		frappe.ui.form.qz_get_printer_list().then((data) => {
			this.printer_list = data;
			const dialog = new frappe.ui.Dialog({
				title: __("Printer Settings"),
				fields: [{
					fieldtype: 'Section Break'
				},
				{
					fieldname: "printer_mapping",
					fieldtype: "Table",
					label: __('Printer Mapping'),
					in_place_edit: true,
					data: this.data,
					get_data: () => {
						return this.data;
					},
					fields: [{
						fieldtype: 'Select',
						fieldname: "print_format",
						default: 0,
						options: this.print_formats,
						read_only: 0,
						in_list_view: 1,
						label: __('Print Format')
					}, {
						fieldtype: 'Select',
						fieldname: "printer",
						default: 0,
						options: this.printer_list,
						read_only: 0,
						in_list_view: 1,
						label: __('Printer')
					}]
				},
				],
				primary_action: function () {
					let printer_mapping = this.get_values()["printer_mapping"];
					if (printer_mapping && printer_mapping.length) {
						let print_format_list = printer_mapping.map(a => a.print_format);
						let has_duplicate = print_format_list.some((item, idx) => print_format_list.indexOf(item) != idx);
						if (has_duplicate)
							frappe.throw(__("Cannot have multiple printers mapped to a single print format."));
					} else {
						printer_mapping = [];
					}
					this.print_format_printer_map = me.get_print_format_printer_map();
					this.print_format_printer_map[me.frm.doctype] = printer_mapping;
					localStorage.print_format_printer_map = JSON.stringify(this.print_format_printer_map);
					this.hide();
				},
				primary_action_label: __('Save')
			});
			dialog.show();
			if (!(this.printer_list && this.printer_list.length)) {
				frappe.throw(__("No Printer is Available."));
			}
		});
	}
});

frappe.ui.get_print_settings = function (pdf, callback, letter_head, pick_columns) {
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
		options: [
			{ "value": "Landscape", "label": __("Landscape") },
			{ "value": "Portrait", "label": __("Portrait") }
		],
		default: "Landscape"
	}];

	if (pick_columns) {
		columns.push(
			{
				label: __("Pick Columns"),
				fieldtype: "Check",
				fieldname: "pick_columns",
			},
			{
				label: __("Select Columns"),
				fieldtype: "MultiCheck",
				fieldname: "columns",
				depends_on: "pick_columns",
				columns: 2,
				options: pick_columns.map(df => ({
					label: __(df.label),
					value: df.fieldname
				}))
			}
		);
	}

	return frappe.prompt(columns, function (data) {
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


// qz tray connection wrapper
//  - allows active and inactive connections to resolve regardless
//  - try to connect once before firing the mimetype launcher
//  - if connection fails, catch the reject, fire the mimetype launcher
//  - after mimetype launcher is fired, try to connect 3 more times
//  - display success/fail message to user
frappe.ui.form.qz_connect = function () {
	return new Promise(function (resolve, reject) {
		frappe.ui.form.qz_init().then(() => {
			if (qz.websocket.isActive()) { // if already active, resolve immediately
				// frappe.show_alert({message: __('QZ Tray Connection Active!'), indicator: 'green'});
				resolve();
			} else {
				// try to connect once before firing the mimetype launcher
				frappe.show_alert({
					message: __('Attempting Connection to QZ Tray...'),
					indicator: 'blue'
				});
				qz.websocket.connect().then(() => {
					frappe.show_alert({
						message: __('Connected to QZ Tray!'),
						indicator: 'green'
					});
					resolve();
				}, function retry(err) {
					if (err.message === 'Unable to establish connection with QZ') {
						// if a connect was not successful, launch the mimetype, try 3 more times
						frappe.show_alert({
							message: __('Attempting to launch QZ Tray...'),
							indicator: 'blue'
						}, 14);
						window.location.assign("qz:launch");
						qz.websocket.connect({
							retries: 3,
							delay: 1
						}).then(() => {
							frappe.show_alert({
								message: __('Connected to QZ Tray!'),
								indicator: 'green'
							});
							resolve();
						},
						() => {
							frappe.throw(__('Error connecting to QZ Tray Application...<br><br> You need to have QZ Tray application installed and running, to use the Raw Print feature.<br><br><a target="_blank" href="https://qz.io/download/">Click here to Download and install QZ Tray</a>.<br> <a target="_blank" href="https://erpnext.com/docs/user/manual/en/setting-up/print/raw-printing">Click here to learn more about Raw Printing</a>.'));
							reject();
						});
					} else {
						frappe.show_alert({
							message: 'QZ Tray ' + err.toString(),
							indicator: 'red'
						}, 14);
						reject();
					}
				});
			}
		});
	});
}

frappe.ui.form.qz_init = function () {
	// Initializing qz tray library
	return new Promise((resolve) => {
		if (typeof qz === "object" && typeof qz.version === "string") {
			// resolve immediately if already Initialized
			resolve();
		} else {
			let qz_required_assets = [
				"/assets/frappe/node_modules/js-sha256/build/sha256.min.js",
				"/assets/frappe/node_modules/qz-tray/qz-tray.js"
			];
			frappe.require(qz_required_assets,() => {
				qz.api.setPromiseType(function promise(resolver) {
					return new Promise(resolver);
				});
				qz.api.setSha256Type(function (data) {
					// Codacy fix
					/*global sha256*/
					return sha256(data);
				});
				resolve();
			});
			// note 'frappe.require' does not have callback on fail. Hence, any failure cannot be communicated to the user.
		}

	});
}

frappe.ui.form.qz_get_printer_list = function () {
	// returns the list of printers that are available to the QZ Tray
	return frappe.ui.form.qz_connect().then(function () {
		return qz.printers.find();
	}).then((data) => {
		return data;
	}).catch((err) => {
		frappe.ui.form.qz_fail(err);
	});
}

frappe.ui.form.qz_success = function () {
	// notify qz successful print
	frappe.show_alert({
		message: __('Print Sent to the printer!'),
		indicator: 'green'
	});
}

frappe.ui.form.qz_fail = function (e) {
	// notify qz errors
	frappe.show_alert({
		message: __("QZ Tray Failed: ") + e.toString(),
		indicator: 'red'
	}, 20);
}
