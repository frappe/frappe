frappe.pages['print'].on_page_load = function(wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
	});

	let print_view = new frappe.ui.form.PrintView(wrapper);

	$(wrapper).bind('show', () => {
		const route = frappe.get_route();
		const doctype = route[1];
		const docname = route[2];
		if (!frappe.route_options || !frappe.route_options.frm) {
			frappe.model.with_doc(doctype, docname, () => {
				let frm = { doctype: doctype, docname: docname };
				frm.doc = frappe.get_doc(doctype, docname);
				frappe.model.with_doctype(doctype, () => {
					frm.meta = frappe.get_meta(route[1]);
					print_view.show(frm);
				});
			});
		} else {
			print_view.frm = frappe.route_options.frm;
			frappe.route_options.frm = null;
			print_view.show(print_view.frm);
		}
	});
};

frappe.ui.form.PrintView = class {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = wrapper.page;
		this.make();
	}

	make() {
		this.print_wrapper = this.page.main.empty().html(
			`<div class="print-preview-wrapper"><div class="print-preview">
				${frappe.render_template('print_skeleton_loading')}
				<iframe class="print-format-container" width="100%" height="0" frameBorder="0" scrolling="no"">
				</iframe>
			</div>
			<div class="page-break-message text-muted text-center text-medium margin-top"></div>
		</div>`
		);

		this.print_settings = frappe.model.get_doc(
			':Print Settings',
			'Print Settings'
		);
		this.setup_toolbar();
		this.setup_menu();
		this.setup_sidebar();
		this.setup_keyboard_shortcuts();
	}

	set_title() {
		this.page.set_title(this.frm.docname);
	}

	setup_toolbar() {
		this.page.set_primary_action(
			__('Print'),
			() => this.printit(), 'printer'
		);

		this.page.add_button(
			__('Full Page'),
			() => this.render_page('/printview?'),
			{ icon: 'full-page' }
		);

		this.page.add_button(
			__('PDF'),
			() => this.render_page('/api/method/frappe.utils.print_format.download_pdf?'),
			{ icon: 'small-file' }
		);

		this.page.add_button(
			frappe.utils.icon('refresh'),
			() => this.refresh_print_format()
		);
	}

	setup_sidebar() {
		this.sidebar = this.page.sidebar.addClass('print-preview-sidebar');

		this.print_sel = this.add_sidebar_item(
			{
				fieldtype: 'Select',
				fieldname: 'print_format',
				label: 'Print Format',
				options: [this.get_default_option_for_select(__('Select Print Format'))],
				change: () => this.refresh_print_format(),
				default: __('Select Print Format')
			},
		).$input;

		this.language_sel = this.add_sidebar_item(
			{
				fieldtype: 'Select',
				fieldname: 'language',
				placeholder: 'Language',
				options: [
					this.get_default_option_for_select(__('Select Language')),
					...this.get_language_options()
				],
				default: __('Select Language'),
				change: () => {
					this.set_user_lang();
					this.preview();
				},
			},
		).$input;

		this.letterhead_selector_df = this.add_sidebar_item(
			{
				fieldtype: 'Autocomplete',
				fieldname: 'letterhead',
				label: __('Select Letterhead'),
				placeholder: __('Select Letterhead'),
				options: [__('No Letterhead')],
				change: () => this.preview(),
				default: this.print_settings.with_letterhead
					? __('No Letterhead')
					: __('Select Letterhead')
			},
		);
		this.letterhead_selector = this.letterhead_selector_df.$input;
		this.sidebar_dynamic_section = $(
			`<div class="dynamic-settings"></div>`
		).appendTo(this.sidebar);
	}

	add_sidebar_item(df, is_dynamic) {
		if (df.fieldtype == 'Select') {
			df.input_class = 'btn btn-default btn-sm';
		}

		let field = frappe.ui.form.make_control({
			df: df,
			parent: is_dynamic ? this.sidebar_dynamic_section : this.sidebar,
			render_input: 1,
		});

		if (df.default != null) {
			field.set_input(df.default);
		}

		return field;
	}

	get_default_option_for_select(value) {
		return {
			label: value,
			value: value,
			disabled: true
		};
	}

	setup_menu() {
		this.page.clear_menu();

		this.page.add_menu_item(__('Print Settings'), () => {
			frappe.set_route('Form', 'Print Settings');
		});

		if (
			frappe.model.get_doc(':Print Settings', 'Print Settings')
				.enable_raw_printing == '1'
		) {
			this.page.add_menu_item(__('Raw Printing Setting'), () => {
				this.printer_setting_dialog();
			});
		}

		if (frappe.user.has_role('System Manager')) {
			this.page.add_menu_item(__('Customize'), () =>
				this.edit_print_format()
			);
		}
	}

	show(frm) {
		this.frm = frm;
		this.set_title();
		this.set_breadcrumbs();
		this.setup_customize_dialog();

		let tasks = [
			this.refresh_print_options,
			this.set_default_print_language,
			this.set_letterhead_options,
			this.preview,
		].map((fn) => fn.bind(this));

		this.setup_additional_settings();
		return frappe.run_serially(tasks);
	}

	set_breadcrumbs() {
		frappe.breadcrumbs.add(this.frm.meta.module, this.frm.doctype);
	}

	setup_additional_settings() {
		this.additional_settings = {};
		this.sidebar_dynamic_section.empty();
		frappe
			.xcall('frappe.printing.page.print.print.get_print_settings_to_show', {
				doctype: this.frm.doc.doctype,
				docname: this.frm.doc.name
			})
			.then((settings) => this.add_settings_to_sidebar(settings));
	}

	add_settings_to_sidebar(settings) {
		for (let df of settings) {
			let field = this.add_sidebar_item({
				...df,
				change: () => {
					const val = field.get_value();
					this.additional_settings[field.df.fieldname] = val;
					this.preview();
				},
			}, true);
		}
	}

	edit_print_format() {
		let print_format = this.get_print_format();
		let is_custom_format =
			print_format.name &&
			print_format.print_format_builder &&
			print_format.standard === 'No';
		let is_standard_but_editable =
			print_format.name && print_format.custom_format;

		if (is_standard_but_editable) {
			frappe.set_route('Form', 'Print Format', print_format.name);
			return;
		}
		if (is_custom_format) {
			frappe.set_route('print-format-builder', print_format.name);
			return;
		}
		// start a new print format
		frappe.prompt(
			[
				{
					label: __('New Print Format Name'),
					fieldname: 'print_format_name',
					fieldtype: 'Data',
					reqd: 1,
				},
				{
					label: __('Based On'),
					fieldname: 'based_on',
					fieldtype: 'Read Only',
					default: print_format.name || 'Standard',
				},
			],
			(data) => {
				frappe.route_options = {
					make_new: true,
					doctype: this.frm.doctype,
					name: data.print_format_name,
					based_on: data.based_on,
				};
				frappe.set_route('print-format-builder');
				this.print_sel.val(data.print_format_name);
			},
			__('New Custom Print Format'),
			__('Start')
		);
	}

	refresh_print_format() {
		this.set_default_print_language();
		this.toggle_raw_printing();
		this.preview();
	}

	// bind_events () {
	// 	// // hide print view on pressing escape, only if there is no focus on any input
	// 	// $(document).on("keydown", function (e) {
	// 	// 	if (e.which === 27 && me.frm && e.target === document.body) {
	// 	// 		me.hide();
	// 	// 	}
	// 	// });
	// }

	setup_customize_dialog() {
		let print_format = this.get_print_format();
		$(document).on('new-print-format', (e) => {
			this.refresh_print_options();
			if (e.print_format) {
				this.print_sel.val(e.print_format);
			}
			// start a new print format
			frappe.prompt(
				[
					{
						label: __('New Print Format Name'),
						fieldname: 'print_format_name',
						fieldtype: 'Data',
						reqd: 1,
					},
					{
						label: __('Based On'),
						fieldname: 'based_on',
						fieldtype: 'Read Only',
						default: print_format.name || 'Standard',
					},
				],
				(data) => {
					frappe.route_options = {
						make_new: true,
						doctype: this.frm.doctype,
						name: data.print_format_name,
						based_on: data.based_on,
					};
					frappe.set_route('print-format-builder');
				},
				__('New Custom Print Format'),
				__('Start')
			);
		});
	}

	setup_keyboard_shortcuts() {
		this.wrapper.find('.print-toolbar a.btn-default').each((i, el) => {
			frappe.ui.keys.get_shortcut_group(this.frm.page).add($(el));
		});
	}

	set_letterhead_options() {
		let letterhead_options = [__('No Letterhead')];
		let default_letterhead;
		let doc_letterhead = this.frm.doc.letter_head;

		return frappe.db
			.get_list('Letter Head', { fields: ['name', 'is_default'], limit: 0 })
			.then((letterheads) => {
				letterheads.map((letterhead) => {
					if (letterhead.is_default) default_letterhead = letterhead.name;
					return letterhead_options.push(letterhead.name);
				});

				this.letterhead_selector_df.set_data(letterhead_options);
				let selected_letterhead = doc_letterhead || default_letterhead;
				if (selected_letterhead)
					this.letterhead_selector.val(selected_letterhead);
			});
	}

	set_user_lang() {
		this.lang_code = this.language_sel.val();
	}

	get_language_options() {
		return frappe.get_languages();
	}

	set_default_print_language() {
		let print_format = this.get_print_format();
		this.lang_code =
			print_format.default_print_language ||
			this.frm.doc.language ||
			frappe.boot.lang;
		this.language_sel.val(this.lang_code);
	}

	toggle_raw_printing() {
		const is_raw_printing = this.is_raw_printing();
		this.wrapper.find('.btn-print-preview').toggle(!is_raw_printing);
		this.wrapper.find('.btn-download-pdf').toggle(!is_raw_printing);
	}

	preview() {
		const $print_format = this.print_wrapper.find('iframe');
		this.$print_format_body = $print_format.contents();
		this.get_print_html((out) => {
			if (!out.html) {
				out.html = this.get_no_preview_html();
			}

			this.setup_print_format_dom(out, $print_format);

			const print_height = $print_format.get(0).offsetHeight;
			const $message = this.wrapper.find('.page-break-message');

			const print_height_inches = frappe.dom.pixel_to_inches(print_height);
			// if contents are large enough, indicate that it will get printed on multiple pages
			// Maximum height for an A4 document is 11.69 inches
			if (print_height_inches > 11.69) {
				$message.text(__('This may get printed on multiple pages'));
			} else {
				$message.text('');
			}
		});
	}

	setup_print_format_dom(out, $print_format) {
		this.print_wrapper.find('.print-format-skeleton').remove();
		let base_url = frappe.urllib.get_base_url();
		let print_css_url = `${base_url}/assets/${frappe.utils.is_rtl(this.lang_code) ? 'css-rtl' : 'css'}/printview.css`;
		this.$print_format_body.find('html').attr('dir', frappe.utils.is_rtl(this.lang_code) ? 'rtl': 'ltr');
		this.$print_format_body.find('html').attr('lang', this.lang_code);
		this.$print_format_body.find('head').html(
			`<style type="text/css">${out.style}</style>
			<link href="${print_css_url}" rel="stylesheet">`
		);

		this.$print_format_body.find('body').html(
			`<div class="print-format print-format-preview">${out.html}</div>`
		);

		this.show_footer();

		this.$print_format_body.find('.print-format').css({
			display: 'flex',
			flexDirection: 'column',
		});

		this.$print_format_body.find('.page-break').css({
			display: 'flex',
			'flex-direction': 'column',
			flex: '1',
		});

		setTimeout(() => {
			$print_format.height(this.$print_format_body.find('.print-format').outerHeight());
		}, 500);
	}

	hide() {
		if (this.frm.setup_done && this.frm.page.current_view_name === 'print') {
			this.frm.page.set_view(
				this.frm.page.previous_view_name === 'print'
					? 'main'
					: this.frm.page.previous_view_name || 'main'
			);
		}
	}

	show_footer() {
		// footer is hidden by default as reqd by pdf generation
		// simple hack to show it in print preview

		this.$print_format_body.find('#footer-html').attr(
			'style',
			`
			display: block !important;
			order: 1;
			margin-top: auto;
			padding-top: var(--padding-xl)
		`
		);
	}

	printit() {
		let me = this;
		frappe.call({
			method:
				'frappe.printing.doctype.print_settings.print_settings.is_print_server_enabled',
			callback: function(data) {
				if (data.message) {
					frappe.call({
						method: 'frappe.utils.print_format.print_by_server',
						args: {
							doctype: me.frm.doc.doctype,
							name: me.frm.doc.name,
							print_format: me.selected_format(),
							no_letterhead: me.with_letterhead(),
							letterhead: this.get_letterhead(),
						},
						callback: function() {},
					});
				} else if (me.get_mapped_printer().length === 1) {
					// printer is already mapped in localstorage (applies for both raw and pdf )
					if (me.is_raw_printing()) {
						me.get_raw_commands(function(out) {
							frappe.ui.form
								.qz_connect()
								.then(function() {
									let printer_map = me.get_mapped_printer()[0];
									let data = [out.raw_commands];
									let config = qz.configs.create(printer_map.printer);
									return qz.print(config, data);
								})
								.then(frappe.ui.form.qz_success)
								.catch((err) => {
									frappe.ui.form.qz_fail(err);
								});
						});
					} else {
						frappe.show_alert(
							{
								message: __('PDF printing via "Raw Print" is not supported.'),
								subtitle: __(
									'Please remove the printer mapping in Printer Settings and try again.'
								),
								indicator: 'info',
							},
							14
						);
						//Note: need to solve "Error: Cannot parse (FILE)<URL> as a PDF file" to enable qz pdf printing.
					}
				} else if (me.is_raw_printing()) {
					// printer not mapped in localstorage and the current print format is raw printing
					frappe.show_alert(
						{
							message: __('Printer mapping not set.'),
							subtitle: __(
								'Please set a printer mapping for this print format in the Printer Settings'
							),
							indicator: 'warning',
						},
						14
					);
					me.printer_setting_dialog();
				} else {
					me.render_page('/printview?', true);
				}
			},
		});
	}

	render_page(method, printit = false) {
		let w = window.open(
			frappe.urllib.get_full_url(
				method +
					'doctype=' +
					encodeURIComponent(this.frm.doc.doctype) +
					'&name=' +
					encodeURIComponent(this.frm.doc.name) +
					(printit ? '&trigger_print=1' : '') +
					'&format=' +
					encodeURIComponent(this.selected_format()) +
					'&no_letterhead=' +
					(this.with_letterhead() ? '0' : '1') +
					'&letterhead=' +
					encodeURIComponent(this.get_letterhead()) +
					'&settings=' +
					encodeURIComponent(JSON.stringify(this.additional_settings)) +
					(this.lang_code ? '&_lang=' + this.lang_code : '')
			)
		);
		if (!w) {
			frappe.msgprint(__('Please enable pop-ups'));
			return;
		}
	}

	get_print_html(callback) {
		let print_format = this.get_print_format();
		if (print_format.raw_printing) {
			callback({
				html: this.get_no_preview_html(),
			});
			return;
		}
		if (this._req) {
			this._req.abort();
		}
		this._req = frappe.call({
			method: 'frappe.www.printview.get_html_and_style',
			args: {
				doc: this.frm.doc,
				print_format: this.selected_format(),
				no_letterhead: !this.with_letterhead() ? 1 : 0,
				letterhead: this.get_letterhead(),
				settings: this.additional_settings,
				_lang: this.lang_code,
			},
			callback: function(r) {
				if (!r.exc) {
					callback(r.message);
				}
			},
		});
	}

	get_letterhead() {
		return this.letterhead_selector.val();
	}

	get_no_preview_html() {
		return `<div class="text-muted text-center" style="font-size: 1.2em;">
			${__('No Preview Available')}
		</div>`;
	}

	get_raw_commands(callback) {
		// fetches rendered raw commands from the server for the current print format.
		frappe.call({
			method: 'frappe.www.printview.get_rendered_raw_commands',
			args: {
				doc: this.frm.doc,
				print_format: this.selected_format(),
				_lang: this.lang_code,
			},
			callback: function(r) {
				if (!r.exc) {
					callback(r.message);
				}
			},
		});
	}

	get_mapped_printer() {
		// returns a list of "print format: printer" mapping filtered by the current print format
		let print_format_printer_map = this.get_print_format_printer_map();
		if (print_format_printer_map[this.frm.doctype]) {
			return print_format_printer_map[this.frm.doctype].filter(
				(printer_map) => printer_map.print_format == this.selected_format()
			);
		} else {
			return [];
		}
	}

	get_print_format_printer_map() {
		// returns the whole object "print_format_printer_map" stored in the localStorage.
		try {
			let print_format_printer_map = JSON.parse(
				localStorage.print_format_printer_map
			);
			return print_format_printer_map;
		} catch (e) {
			return {};
		}
	}

	refresh_print_options() {
		this.print_formats = frappe.meta.get_print_formats(this.frm.doctype);
		const print_format_select_val = this.print_sel.val();
		this.print_sel.empty().add_options([
			this.get_default_option_for_select(__('Select Print Format')),
			...this.print_formats
		]);
		return this.print_formats.includes(print_format_select_val)
			&& this.print_sel.val(print_format_select_val);
	}

	selected_format() {
		return (
			this.print_sel.val() || this.frm.meta.default_print_format || 'Standard'
		);
	}

	is_raw_printing(format) {
		return this.get_print_format(format).raw_printing === 1;
	}

	get_print_format(format) {
		let print_format = {};
		if (!format) {
			format = this.selected_format();
		}

		if (locals['Print Format'] && locals['Print Format'][format]) {
			print_format = locals['Print Format'][format];
		}

		return print_format;
	}

	with_letterhead() {
		return cint(this.get_letterhead() !== __('No Letterhead'));
	}

	set_style(style) {
		frappe.dom.set_style(style || frappe.boot.print_css, 'print-style');
	}

	printer_setting_dialog() {
		// dialog for the Printer Settings
		this.print_format_printer_map = this.get_print_format_printer_map();
		this.data = this.print_format_printer_map[this.frm.doctype] || [];
		this.printer_list = [];
		frappe.ui.form.qz_get_printer_list().then((data) => {
			this.printer_list = data;
			const dialog = new frappe.ui.Dialog({
				title: __('Printer Settings'),
				fields: [
					{
						fieldtype: 'Section Break',
					},
					{
						fieldname: 'printer_mapping',
						fieldtype: 'Table',
						label: __('Printer Mapping'),
						in_place_edit: true,
						data: this.data,
						get_data: () => {
							return this.data;
						},
						fields: [
							{
								fieldtype: 'Select',
								fieldname: 'print_format',
								default: 0,
								options: this.print_formats,
								read_only: 0,
								in_list_view: 1,
								label: __('Print Format'),
							},
							{
								fieldtype: 'Select',
								fieldname: 'printer',
								default: 0,
								options: this.printer_list,
								read_only: 0,
								in_list_view: 1,
								label: __('Printer'),
							},
						],
					},
				],
				primary_action: () => {
					let printer_mapping = dialog.get_values()['printer_mapping'];
					if (printer_mapping && printer_mapping.length) {
						let print_format_list = printer_mapping.map((a) => a.print_format);
						let has_duplicate = print_format_list.some(
							(item, idx) => print_format_list.indexOf(item) != idx
						);
						if (has_duplicate)
							frappe.throw(
								__(
									'Cannot have multiple printers mapped to a single print format.'
								)
							);
					} else {
						printer_mapping = [];
					}
					dialog.print_format_printer_map = this.get_print_format_printer_map();
					dialog.print_format_printer_map[this.frm.doctype] = printer_mapping;
					localStorage.print_format_printer_map = JSON.stringify(
						dialog.print_format_printer_map
					);
					dialog.hide();
				},
				primary_action_label: __('Save'),
			});
			dialog.show();
			if (!(this.printer_list && this.printer_list.length)) {
				frappe.throw(__('No Printer is Available.'));
			}
		});
	}
};
