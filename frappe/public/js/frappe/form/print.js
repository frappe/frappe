frappe.provide("frappe.ui.form");

// init qz tray library
qz.api.setPromiseType(function promise(resolver) {
	return new Promise(resolver); 
});
qz.api.setSha256Type(function(data) { 
	return sha256(data); 
});

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

		this.wrapper.find(".btn-qz-settings").click(function () {
			me.qz_setting_dialog()
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
			me.wrapper.find(".btn-print-preview").toggle(true);
			me.wrapper.find(".btn-download-pdf").toggle(false);
			me.set_style();
			me.preview_old_style();		
		} 
		else if (this.is_raw_printing()){
			me.wrapper.find(".btn-print-preview").toggle(false);
			me.wrapper.find(".btn-download-pdf").toggle(false);
			me.preview();
		}
		else {
			me.wrapper.find(".btn-print-preview").toggle(true);
			me.wrapper.find(".btn-download-pdf").toggle(true);
			me.preview();
		}
	},
	preview: function () {
		var me = this;
		this.get_print_html(function (out) {
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
				} 
				else if(me.get_mapped_printer().length === 1){
					// printer is already mapped in localstorage (applies for both raw and pdf )
					if(me.is_raw_printing()){
						me.get_raw_commands(function(out) {
							let printer_map = me.get_mapped_printer()[0];
							let config = qz.configs.create(printer_map.printer);
							let data = [out.raw_commands];
							frappe.ui.form.qz_connect().then(function(){
								return qz.print(config,data);
							}).then(frappe.ui.form.qz_success).catch((err)=>{
								frappe.ui.form.qz_fail(err);
							})
						})
					}
					else{
						frappe.show_alert({message:__('PDF Printing via QZ is not yet supported. Please remove QZ printer mapping for this Print format and try again.'),indicator:'blue'},14);
						//Note: need to solve "Error: Cannot parse (FILE)<URL> as a PDF file" to enable qz pdf printing.

						// // use pdf method print method of qz
						// let printer_map = me.get_mapped_printer()[0]
						// let config = qz.configs.create(printer_map.printer)
						// let pdf_url = frappe.urllib.get_full_url("/api/method/frappe.utils.print_format.download_pdf?"
						// 									+ "doctype=" + encodeURIComponent(me.frm.doc.doctype)
						// 									+ "&name=" + encodeURIComponent(me.frm.doc.name)
						// 									+ "&format=" + me.selected_format()
						// 									+ "&no_letterhead=" + (me.with_letterhead() ? "0" : "1")
						// 									+ (me.lang_code ? ("&_lang=" + me.lang_code) : ""))
						// let data = [{type: 'pdf', data: pdf_url}]
						// frappe.ui.form.qz_connect().then(function(){
						// 	return qz.print(config,data);
						// }).then(frappe.ui.form.qz_success).catch((err)=>{
						// 	frappe.ui.form.qz_fail(err);
						// })
					}
				}
				else if(me.is_raw_printing()) {
					frappe.show_alert({message:__('Please set a printer mapping for this print format in the QZ Settings'),indicator:'blue'},14);
					me.qz_setting_dialog();
				}
				else {
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
	get_raw_commands: function (callback) {
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
	get_mapped_printer: function() {
		if(localStorage && localStorage.print_format_printer_map 
			&& JSON.parse(localStorage.print_format_printer_map)[this.frm.doctype]) {
			return (JSON.parse(localStorage.print_format_printer_map)[this.frm.doctype])
				.filter((printer_map)=> printer_map.print_format == this.selected_format());
		}
		else {
			return [];
		}
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
	is_raw_printing: function (format) {
		return this.get_print_format(format).raw_printing === true;
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
	qz_setting_dialog: function() {
		var me = this;
		if (localStorage && localStorage.print_format_printer_map)
			this.print_format_printer_map = JSON.parse(localStorage.print_format_printer_map);
		else
			this.print_format_printer_map = {};
		this.data = [];
		this.data = this.print_format_printer_map[this.frm.doctype] || [];
		this.printer_list = [];
		frappe.ui.form.qz_get_printer_list().then((data)=>{
			this.printer_list = data;
			if (!(this.printer_list && this.printer_list.length)) {
				frappe.throw(__("No Printer is Available."));
			}
			const dialog = new frappe.ui.Dialog({
				title: __("QZ Tray Print Settings"),
				fields: [
					{fieldtype:'Section Break'},
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
							fieldtype:'Select',
							fieldname:"print_format",
							default: 0,
							options: this.print_formats,
							read_only: 0,
							in_list_view: 1,
							label: __('Print Format')
						}, {
							fieldtype:'Select',
							fieldname:"printer",
							default: 0,
							options: this.printer_list,
							read_only: 0,
							in_list_view: 1,
							label: __('Printer')
						}]
					},
				],
				primary_action: function() {
					let printer_mapping = this.get_values()["printer_mapping"];
					if (printer_mapping && printer_mapping.length) {
						let print_format_list = printer_mapping.map(a => a.print_format);
						let has_duplicate = print_format_list.some((item, idx) => print_format_list.indexOf(item) != idx  );
						if (has_duplicate)
							frappe.throw(__("Cannot have multiple printers mapped to a single print format."));
					}
					else {
						printer_mapping = [];
					}
					if (localStorage && localStorage.print_format_printer_map)
						this.print_format_printer_map = JSON.parse(localStorage.print_format_printer_map);
					else
						this.print_format_printer_map = {};
					this.print_format_printer_map[me.frm.doctype] = printer_mapping;
					localStorage.print_format_printer_map = JSON.stringify(this.print_format_printer_map);
					this.hide();
				},
				primary_action_label: __('Save')
			});
			dialog.show();
		});
		
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


// qz connection wrapper
//  - allows active and inactive connections to resolve regardless
//  - try to connect once before firing the mimetype launcher
//  - if connection fails, catch the reject, fire the mimetype launcher
//  - after mimetype launcher is fired, try to connect 3 more times
//  - display success/fail meaasges to user
frappe.ui.form.qz_connect = function() {
	return new Promise(function(resolve, reject) {
		if (qz.websocket.isActive()) {	// if already active, resolve immediately
			// frappe.show_alert({message: __('QZ Tray Connection Active!'), indicator: 'green'});
			resolve();
		} 
		else {
			// try to connect once before firing the mimetype launcher
			frappe.show_alert({message: __('Attemting Connection to QZ Tray!'), indicator: 'blue'});
			qz.websocket.connect().then(()=>{
				frappe.show_alert({message: __('Connected to QZ Tray!'), indicator: 'green'});
				resolve();
			}, function retry(err) {
				if (err.message === 'Unable to establish connection with QZ'){
					// if a connect was not succesful, launch the mimetime, try 3 more times
					frappe.show_alert({message: __('Attemting to launch QZ Tray!'), indicator: 'blue'},14);
					window.location.assign("qz:launch");
					qz.websocket.connect({ retries: 3, delay: 1 }).then(()=>{
						frappe.show_alert({message: __('Connected to QZ Tray!'), indicator: 'green'});
						resolve();
					}, (err)=>{
						frappe.show_alert({message: __('Error connecting to QZ Tray! <a href="https://qz.io/download/">Click here to Download QZ Tray</a>'), indicator: 'red'},14);
						console.error("qz error:",err)
						reject();
					});
			}
			else{
				frappe.show_alert({message: 'QZ Tray '+err.toString(), indicator: 'red'},14);
				reject();
			}
            });
        }
    });
}

frappe.ui.form.qz_get_printer_list = function(){
	return frappe.ui.form.qz_connect().then(function(){
		return qz.printers.find()
	}).then((data)=>{
		return data
	}).catch((err)=>{
		frappe.ui.form.qz_fail(err);
	});
}

// notify qz successful print
frappe.ui.form.qz_success = function() { 
    frappe.show_alert({message: __('QZ print complete!'), indicator: 'green'});
}

// notify qz errors
frappe.ui.form.qz_fail = function(e) {
	console.error("qz error:",e)
    frappe.show_alert({message:__("QZ Tray Failed") + e.toString(), indicator:'red'},20);
}


// flow for action after print button is clicked
// - if printer is already mapped in localstorage (applies for both raw and pdf )
// 	- qz_connect()
// 	- search for configured printer and create config
// 		- if the above fails throw error with printer not found. (and instructions/options to remove all mapping from localstorage for this printer)
//  - if raw_printing call appropriate qz fn
//  - else call pdf and then call appropriate qz fn with that pdf
// - else if raw_printing == true
// 	- qz_connect()
// 	- if search returns printers
// 		- show modal with list of printer and ask to map
// 		- store in LocalStorage
// 	- else throw error that no printer is available

