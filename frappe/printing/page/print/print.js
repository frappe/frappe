const STANDARD_PRINT_STYLES = ["Redesign", "Modern", "Classic", "Bold", "Striped", "Monochrome"];

frappe.pages["print"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
	});

	let print_view = new frappe.ui.form.PrintView(wrapper);

	$(wrapper).on("hide", () => frappe.app?.sidebar?.unfold_after_leaving_page());
	$(wrapper).bind("show", () => {
		frappe.app?.sidebar?.fold_for_page();
		const route = frappe.get_route();
		const doctype = route[1];
		const docname = route.slice(2).join("/");
		if (!frappe.route_options || !frappe.route_options.frm) {
			frappe.model.with_doc(doctype, docname, () => {
				let frm = { doctype: doctype, docname: docname };
				frm.doc = frappe.get_doc(doctype, docname);
				frappe.model.with_doctype(doctype, () => {
					frm.meta = frappe.get_meta(route[1]);
					frm.meta.module &&
						frappe.app.sidebar?.show_sidebar_for_module?.(frm.meta.module);
					print_view.show(frm);
				});
			});
		} else {
			print_view.frm = frappe.route_options.frm.doctype
				? frappe.route_options.frm
				: frappe.route_options.frm.frm;
			delete frappe.route_options.frm;
			let meta = print_view.frm.meta;
			print_view.show(print_view.frm);
		}
	});
};

frappe.ui.form.PrintView = class {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = wrapper.page;
		this.make();

		this.wrapper.on("show", () => {
			this.page.sidebar.show();
		});
	}

	make() {
		this.print_wrapper = this.page.main.empty().html(
			`<div class="print-preview-wrapper"><div class="print-preview">
				${frappe.render_template("print_skeleton_loading")}
				<iframe class="print-format-container" width="100%" height="0" frameBorder="0" scrolling="no">
				</iframe>
			</div>
			<div class="page-break-message text-muted text-center text-medium margin-top"></div>
		</div>
		<div class="preview-beta-wrapper">
			<iframe width="100%" height="0" frameBorder="0"></iframe>
			<div class="print-preview-bar">
				<button class="es-button" data-variant="ghost" data-size="sm" data-icon-button="true" data-action="prev-page" aria-label="${__(
					"Previous page"
				)}">${frappe.utils.icon("chevron-up", "sm")}</button>
				<span class="print-preview-bar-label page-label"></span>
				<button class="es-button" data-variant="ghost" data-size="sm" data-icon-button="true" data-action="next-page" aria-label="${__(
					"Next page"
				)}">${frappe.utils.icon("chevron-down", "sm")}</button>
				<span class="print-preview-bar-divider"></span>
				<button class="es-button" data-variant="ghost" data-size="sm" data-icon-button="true" data-action="zoom-out" aria-label="${__(
					"Zoom out"
				)}">${frappe.utils.icon("minus", "sm")}</button>
				<span class="print-preview-bar-label zoom-label"></span>
				<button class="es-button" data-variant="ghost" data-size="sm" data-icon-button="true" data-action="zoom-in" aria-label="${__(
					"Zoom in"
				)}">${frappe.utils.icon("plus", "sm")}</button>
				<button class="es-button" data-variant="ghost" data-size="sm" data-action="fit">${__(
					"Fit"
				)}</button>
			</div>
		</div>
		`
		);
		this.zoom = 1;
		this.setup_preview_bar();

		const htmlSkeleton = `
		<!DOCTYPE html>
		<html lang="en">
			<head>
				<meta charset="UTF-8" />
				<meta name="viewport" content="width=device-width, initial-scale=1.0" />
			</head>
			<body>
			</body>
		</html>
		`;
		document.querySelector("iframe.print-format-container").srcdoc = htmlSkeleton;

		this.print_settings = frappe.model.get_doc(":Print Settings", "Print Settings");
		this.setup_menu();
		this.setup_toolbar();
		this.setup_sidebar();
		this.setup_keyboard_shortcuts();
	}

	set_title() {
		this.page.set_title(__(this.frm.docname));
	}

	setup_toolbar() {
		this.page.set_primary_action(__("Print"), () => this.printit(), "printer");

		this.page.add_button(__("PDF"), () => this.render_pdf(), { icon: "download" });

		this.page.add_button(__("Email"), () => this.email_doc(), { icon: "mail" });

		if (frappe.is_mobile()) {
			this.page.add_button(__("Form"), () => this.go_to_form_view(), {
				icon: "file-spreadsheet",
			});
		} else {
			this.page.add_action_icon("file-pen", () => this.go_to_form_view(), "", __("Form"));
		}
	}

	setup_sidebar() {
		this.sidebar = this.page.sidebar.addClass("print-preview-sidebar");
		this.add_sidebar_heading(__("Format"));

		this.print_format_field = this.add_sidebar_item({
			fieldtype: "Link",
			fieldname: "print_format",
			options: "Print Format",
			label: __("Print Format"),
			get_query: () => {
				return {
					filters: {
						doc_type: this.frm.doctype,
						print_format_for: ["in", ["DocType", ""]],
					},
				};
			},
			change: () => this.refresh_print_format(),
		});
		this.print_format_selector = this.print_format_field.$input;

		this.language_field = this.add_sidebar_item({
			fieldtype: "Link",
			fieldname: "language",
			label: __("Language"),
			options: "Language",
			change: () => {
				this.set_user_lang();
				this.preview();
			},
		});
		this.language_selector = this.language_field.$input;

		let description = "";
		if (!cint(this.print_settings.repeat_header_footer)) {
			description =
				"<div class='form-message yellow p-3 mt-3'>" +
				__("Footer might not be visible as {0} option is disabled</div>", [
					`<a href="/desk/print-settings/Print Settings">${__(
						"Repeat Header and Footer"
					)}</a>`,
				]);
		}
		const print_view = this;
		this.letterhead_selector = this.add_sidebar_item({
			fieldtype: "Link",
			fieldname: "letterhead",
			options: "Letter Head",
			label: __("Letter Head"),
			description: description,
			get_query: () => {
				return { filters: { letter_head_for: "DocType" } };
			},
			change: function () {
				this.set_description(this.get_value() ? description : "");
				print_view.preview();
			},
		}).$input;
		this.setup_style_picker();
		this.setup_page_settings();
		this.sidebar_dynamic_section = $(`<div class="dynamic-settings"></div>`).appendTo(
			this.sidebar
		);
	}

	add_sidebar_heading(label, parent) {
		return $(`<div class="print-sidebar-heading">${label}</div>`).appendTo(
			parent || this.sidebar
		);
	}

	setup_page_settings() {
		this.page_overrides = {};
		this.page_settings = $(`<div class="print-page-settings"></div>`).appendTo(this.sidebar);
		this.add_sidebar_heading(__("Page"), this.page_settings);
		const set = (key, value) => {
			if (value === "" || value == null) delete this.page_overrides[key];
			else this.page_overrides[key] = value;
			this.preview();
		};
		const make = (df) =>
			frappe.ui.form.make_control({ df, parent: this.page_settings, render_input: 1 });
		make({
			fieldtype: "Select",
			fieldname: "pdf_page_size",
			label: __("Paper Size"),
			options: [
				{ label: __("Default"), value: "" },
				"A4",
				"A5",
				"A3",
				"Letter",
				"Legal",
				"Tabloid",
			],
			change() {
				set("pdf_page_size", this.get_value());
			},
		});
		make({
			fieldtype: "Select",
			fieldname: "page_orientation",
			label: __("Orientation"),
			options: [
				{ label: __("Portrait"), value: "Portrait" },
				{ label: __("Landscape"), value: "Landscape" },
			],
			change() {
				set("page_orientation", this.get_value() === "Landscape" ? "Landscape" : "");
			},
		}).set_input("Portrait");
	}

	make_default_format() {
		const format = this.selected_format();
		if (format === "Standard") {
			frappe.show_alert({
				message: __("Standard is used when no default is set"),
				indicator: "blue",
			});
			return;
		}
		frappe.call("frappe.printing.doctype.print_format.print_format.make_default", {
			name: format,
		});
	}

	get_print_settings_param() {
		const settings = Object.assign({}, this.additional_settings);
		if (this.renders_via_generator(this.get_print_format())) {
			Object.assign(settings, this.page_overrides);
		}
		if (this.selected_format() === "Standard") {
			if (this.print_font) settings.print_font = this.print_font;
		}
		return settings;
	}

	setup_style_picker() {
		this.style_picker = $(`<div class="print-style-picker">
			<div class="print-sidebar-heading">${__("Style")}</div>
			<div class="form-group"><div class="print-style-options"></div></div>
		</div>`).appendTo(this.sidebar);
		const print_view = this;
		frappe.ui.form.make_control({
			df: {
				fieldtype: "Select",
				fieldname: "print_font",
				label: __("Font"),
				options: [
					{ label: __("Default"), value: "" },
					"Inter",
					"Roboto",
					"Open Sans",
					"Lato",
					"Noto Sans",
					"IBM Plex Sans",
					"Lora",
					"Merriweather",
				],
				change() {
					print_view.print_font = this.get_value();
					print_view.preview();
				},
			},
			parent: this.style_picker,
			render_input: 1,
		});
		this.style_picker.on("click", ".print-style-option", (e) => {
			this.print_style = e.currentTarget.dataset.style;
			this.render_style_options();
			this.preview();
		});
		frappe.xcall("frappe.printing.page.print.print.get_print_styles").then((names) => {
			const rank = (name) =>
				STANDARD_PRINT_STYLES.includes(name)
					? STANDARD_PRINT_STYLES.indexOf(name)
					: STANDARD_PRINT_STYLES.length;
			this.print_styles = names.sort((a, b) => rank(a) - rank(b));
			this.render_style_options();
		});
	}

	render_style_options() {
		const styles = this.print_styles || [];
		const active = this.print_style || this.print_settings.print_style;
		this.style_picker.find(".print-style-options").html(
			styles
				.map((name) => {
					const slug = frappe.scrub(name).replace(/_/g, "-");
					const selected = name === active;
					return `<button type="button" class="print-style-option${
						selected ? " active" : ""
					}" data-style="${frappe.utils.escape_html(name)}" aria-pressed="${selected}">
						<span class="print-style-thumb print-style-thumb--${frappe.utils.escape_html(slug)}">
							<span class="thumb-label"></span>
							<span class="thumb-fields"><i></i><i></i></span>
							<span class="thumb-table"><i></i><i></i><i></i></span>
						</span>
						<span class="print-style-name">${frappe.utils.escape_html(this.print_style_label(name))}</span>
					</button>`;
				})
				.join("")
		);
		this.toggle_style_picker();
	}

	print_style_label(name) {
		if (name === "Redesign") return __("Default");
		return STANDARD_PRINT_STYLES.includes(name) ? __(name) : name;
	}

	toggle_style_picker() {
		this.style_picker?.toggle(
			this.selected_format() === "Standard" && !!(this.print_styles || []).length
		);
		this.page_settings?.toggle(this.renders_via_generator(this.get_print_format()));
	}

	get_print_style() {
		if (this.selected_format() !== "Standard") return "";
		return this.print_style || this.print_settings.print_style || "";
	}

	add_sidebar_item(df, is_dynamic) {
		if (df.fieldtype == "Select") {
			df.input_class = "btn btn-default btn-sm text-left";
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

	setup_menu() {
		this.page.clear_menu();

		this.page.add_menu_item(__("Full Page"), () => this.render_page("/printview?"));
		this.page.add_menu_item(
			__("Refresh"),
			() => this.refresh_print_format(),
			false,
			"Shift+R"
		);
		if (frappe.model.can_write("Print Format")) {
			this.page.add_menu_item(__("Set as Default Format"), () => this.make_default_format());
		}

		this.page.add_menu_item(__("Print Settings"), () => {
			frappe.set_route("Form", "Print Settings");
		});

		if (this.print_settings.enable_raw_printing == "1") {
			this.page.add_menu_item(__("Raw Printing Setting"), () => {
				this.printer_setting_dialog();
			});
		}

		if (frappe.model.can_create("Print Format")) {
			this.page.add_menu_item(__("Customize"), () => this.edit_print_format());
		}

		if (cint(this.print_settings.enable_print_server)) {
			this.page.add_menu_item(__("Select Network Printer"), () =>
				this.network_printer_setting_dialog()
			);
		}
	}

	show(frm) {
		this.frm = frm;
		this.set_title();
		this.set_breadcrumbs();
		this.setup_customize_dialog();

		let tasks = [
			this.set_default_print_format,
			this.set_default_print_language,
			this.set_default_letterhead,
			this.preview,
		].map((fn) => fn.bind(this));

		this.setup_additional_settings();
		return frappe.run_serially(tasks);
	}

	set_breadcrumbs() {
		const items = frappe.ui.form.get_breadcrumbs(this.frm);
		// the form is one page back from here, so the document stays a way to reach it
		items[items.length - 1].href = `/desk/${frappe.router.slug(
			this.frm.doctype
		)}/${encodeURIComponent(this.frm.docname)}`;
		items.push({ label: __("Print") });
		this.page.set_breadcrumbs(items);
	}

	setup_additional_settings() {
		this.additional_settings = {};
		this.sidebar_dynamic_section.empty();
		frappe
			.xcall("frappe.printing.page.print.print.get_print_settings_to_show", {
				doctype: this.frm.doc.doctype,
				docname: this.frm.doc.name,
			})
			.then((settings) => this.add_settings_to_sidebar(settings));
	}

	add_settings_to_sidebar(settings) {
		for (let df of settings) {
			let field = this.add_sidebar_item(
				{
					...df,
					change: () => {
						const val = field.get_value();
						this.additional_settings[field.df.fieldname] = val;
						this.preview();
					},
				},
				true
			);
		}
	}

	edit_print_format() {
		let print_format = this.get_print_format();
		let is_custom_format =
			print_format.name &&
			(print_format.print_format_builder || print_format.print_format_builder_beta) &&
			print_format.standard === "No";

		let is_standard_jinja_custom =
			print_format.standard === "Yes" &&
			print_format.custom_format &&
			print_format.print_format_type === "Jinja";

		if (is_standard_jinja_custom) {
			let doc = {
				...frappe.get_doc(":Print Format", print_format.name),
				doctype: "Print Format",
			};
			frappe.model.with_doctype("Print Format", () => {
				let newdoc = frappe.model.copy_doc(doc);
				frappe.set_route("Form", "Print Format", newdoc.name);
			});
			return;
		}

		let is_editable = print_format.name && print_format.custom_format;

		if (is_editable) {
			frappe.model.clear_doc("Print Format", print_format.name);
			frappe.set_route("Form", "Print Format", print_format.name);
			return;
		}

		if (is_custom_format) {
			frappe.set_route("print-format-builder", print_format.name);
			return;
		}
		// start a new print format
		frappe.prompt(
			[
				{
					label: __("New Print Format Name"),
					fieldname: "print_format_name",
					fieldtype: "Data",
					reqd: 1,
				},
				{
					label: __("Based On"),
					fieldname: "based_on",
					fieldtype: "Read Only",
					default: print_format.name || "Standard",
				},
			],
			(data) => {
				frappe.call({
					method: "frappe.printing.doctype.print_format.print_format.create_custom_format",
					args: {
						doctype: this.frm.doctype,
						name: data.print_format_name,
						based_on: data.based_on,
					},
					callback: (r) => {
						if (r.message) {
							frappe.set_route("print-format-builder", r.message.name);
							this.set_print_format_value(data.print_format_name);
						}
					},
				});
			},
			__("New Custom Print Format"),
			__("Start")
		);
	}

	refresh_print_format() {
		this.toggle_style_picker();
		this.set_default_print_language();
		this.toggle_raw_printing();
		this.update_letterhead_for_print_format().then(() => this.preview());
	}

	update_letterhead_for_print_format() {
		const format_name = this.selected_format();
		if (!format_name || format_name === "Standard") {
			return this.set_default_letterhead();
		}
		return frappe
			.call({
				method: "frappe.client.get",
				args: { doctype: "Print Format", name: format_name },
			})
			.then((r) => {
				let letter_head = null;
				try {
					letter_head = r.message?.format_data
						? JSON.parse(r.message.format_data)?.letter_head
						: null;
				} catch (_) {
					// malformed format_data — fall through to default letterhead
				}
				if (letter_head) {
					this.letterhead_selector.val(letter_head);
				} else if (letter_head === "") {
					this.letterhead_selector.val("");
				} else {
					return this.set_default_letterhead();
				}
			});
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
		$(document).on("new-print-format", (e) => {
			frappe.prompt(
				[
					{
						label: __("New Print Format Name"),
						fieldname: "print_format_name",
						fieldtype: "Data",
						reqd: 1,
					},
					{
						label: __("Based On"),
						fieldname: "based_on",
						fieldtype: "Read Only",
						default: print_format.name || "Standard",
					},
				],
				(data) => {
					frappe.call({
						method: "frappe.printing.doctype.print_format.print_format.create_custom_format",
						args: {
							doctype: this.frm.doctype,
							name: data.print_format_name,
							based_on: data.based_on,
						},
						callback: (r) => {
							if (r.message) {
								frappe.set_route("print-format-builder", r.message.name);
							}
						},
					});
				},
				__("New Custom Print Format"),
				__("Start")
			);
		});
	}

	setup_preview_bar() {
		this.preview_bar = this.print_wrapper.find(".print-preview-bar");
		this.preview_bar.on("click", "[data-action]", (e) => {
			const action = e.currentTarget.dataset.action;
			if (action === "zoom-in") this.set_zoom(this.zoom + 0.1);
			else if (action === "zoom-out") this.set_zoom(this.zoom - 0.1);
			else if (action === "fit") this.fit_zoom();
			else if (action === "next-page") this.go_to_page(this.current_page + 1);
			else if (action === "prev-page") this.go_to_page(this.current_page - 1);
		});
	}

	on_preview_load(iframe) {
		this.preview_frame = iframe;
		const doc = iframe.contentDocument;
		if (!doc?.body) return;
		this.apply_zoom();
		doc.addEventListener("scroll", () => this.update_page_label());
		doc.addEventListener("keydown", (e) => this.handle_print_keys(e));
		this.update_page_label();
	}

	page_metrics() {
		const doc = this.preview_frame?.contentDocument;
		if (!doc?.body) return null;
		const body = doc.body;
		const page_height = parseFloat(getComputedStyle(body).minHeight) || body.offsetHeight;
		const body_rect = body.getBoundingClientRect();
		const scale = body.offsetHeight / (body_rect.height || 1);
		const bottom_of = (el) => (el.getBoundingClientRect().bottom - body_rect.top) * scale;
		const height_of = (el) => (el ? el.getBoundingClientRect().height * scale : 0);
		const header = doc.querySelector(".document-header-content");
		const repeated = this.print_settings?.repeat_header_footer
			? (header ? bottom_of(header) - parseFloat(getComputedStyle(body).paddingTop) : 0) +
			  height_of(doc.querySelector(".document-footer-content"))
			: 0;
		const starts = [0];
		const fill = (start, end) => {
			const step = () =>
				starts.length > 1
					? Math.max(page_height - repeated, page_height / 4)
					: page_height;
			while (end - start > step() + 1) {
				start += step();
				starts.push(start);
			}
			return start;
		};
		let start = 0;
		doc.querySelectorAll(".section.page-break").forEach((section) => {
			const end = bottom_of(section);
			start = fill(start, end);
			if (end < body.offsetHeight - 1) {
				start = end;
				starts.push(start);
			}
		});
		fill(start, body.offsetHeight);
		return { doc, body, starts, pages: starts.length };
	}

	update_page_label() {
		const m = this.page_metrics();
		if (!m) return;
		const el = m.doc.scrollingElement;
		const middle = (el.scrollTop + el.clientHeight / 2) / this.zoom - m.body.offsetTop;
		const at_end = el.scrollTop + el.clientHeight >= el.scrollHeight - 2;
		this.current_page = at_end
			? m.pages
			: Math.max(1, m.starts.filter((start) => start <= middle).length);
		this.preview_bar
			.find(".page-label")
			.text(__("Page {0} of {1}", [this.current_page, m.pages]));
		this.preview_bar.find("[data-action=prev-page]").prop("disabled", this.current_page <= 1);
		this.preview_bar
			.find("[data-action=next-page]")
			.prop("disabled", this.current_page >= m.pages);
	}

	go_to_page(page) {
		const m = this.page_metrics();
		if (!m) return;
		page = Math.min(m.pages, Math.max(1, page));
		m.doc.scrollingElement.scrollTo({
			top: (m.body.offsetTop + m.starts[page - 1]) * this.zoom,
			behavior: "smooth",
		});
	}

	set_zoom(zoom) {
		this.zoom = Math.min(2, Math.max(0.5, Math.round(zoom * 10) / 10));
		this.apply_zoom();
	}

	apply_zoom() {
		const doc = this.preview_frame?.contentDocument;
		if (doc?.documentElement) doc.documentElement.style.zoom = this.zoom;
		this.preview_bar.find(".zoom-label").text(`${Math.round(this.zoom * 100)}%`);
		this.update_page_label();
	}

	fit_zoom() {
		const m = this.page_metrics();
		if (!m) return;
		const available = this.preview_frame.clientWidth - 64;
		this.set_zoom(available / m.body.offsetWidth);
	}

	handle_print_keys(e) {
		if (!(e.ctrlKey || e.metaKey) || e.altKey) return;
		const key = e.key.toLowerCase();
		if (key === "p") {
			e.preventDefault();
			e.shiftKey ? this.render_pdf() : this.printit();
		} else if (key === "e" && e.shiftKey) {
			e.preventDefault();
			this.email_doc();
		}
	}

	email_doc() {
		const settings = this.get_print_settings_param();
		const print_options = {
			print_format: this.selected_format(),
			letter_head: this.letterhead_selector.val() || "",
			print_style: this.get_print_style() || undefined,
			print_settings: Object.keys(settings).length ? settings : undefined,
		};
		const set_print_options = (composer) => {
			if (this.lang_code) composer.dialog.set_value("print_language", this.lang_code);
		};
		const form = this.frm.email_doc
			? this.frm
			: frappe.views.formview?.[this.frm.doctype]?.frm;
		if (form && form.docname === this.frm.docname) {
			set_print_options(form.email_doc(undefined, print_options));
			return;
		}
		frappe.set_route("Form", this.frm.doctype, this.frm.docname).then(() => {
			const frm = frappe.views.formview?.[this.frm.doctype]?.frm;
			frm && set_print_options(frm.email_doc(undefined, print_options));
		});
	}

	setup_keyboard_shortcuts() {
		this.wrapper.find(".print-toolbar a.btn-default").each((i, el) => {
			frappe.ui.keys.get_shortcut_group(this.frm.page).add($(el));
		});

		[
			["ctrl+p", () => this.printit(), __("Print")],
			["ctrl+shift+p", () => this.render_pdf(), __("Download PDF")],
			["ctrl+shift+e", () => this.email_doc(), __("Email")],
		].forEach(([shortcut, action, description]) => {
			frappe.ui.keys.add_shortcut({
				shortcut,
				action: (e) => {
					e?.preventDefault?.();
					action();
				},
				page: this.page,
				description,
				ignore_inputs: true,
			});
		});
	}

	set_default_letterhead() {
		const get_default = () =>
			frappe.db
				.get_value(
					"Letter Head",
					{ disabled: 0, is_default: 1, letter_head_for: "DocType" },
					"name"
				)
				.then(({ message }) => {
					if (message?.name) this.letterhead_selector.val(message.name);
				});

		if (!this.frm.doc.letter_head) return get_default();

		return frappe.db
			.get_value("Letter Head", { name: this.frm.doc.letter_head, disabled: 0 }, "name")
			.then(({ message }) =>
				message?.name ? this.letterhead_selector.val(message.name) : get_default()
			);
	}

	set_user_lang() {
		this.lang_code = this.language_field
			? this.language_field.get_value()
			: this.language_selector.val();
	}

	set_default_print_language() {
		let print_format = this.get_print_format();
		this.lang_code =
			this.frm.doc.language || print_format.default_print_language || frappe.boot.lang;
		if (this.language_field) this.language_field.set_input(this.lang_code);
		else this.language_selector.val(this.lang_code);
	}

	toggle_raw_printing() {
		const is_raw_printing = this.is_raw_printing();
		this.wrapper.find(".btn-print-preview").toggle(!is_raw_printing);
		this.wrapper.find(".btn-download-pdf").toggle(!is_raw_printing);
	}

	renders_via_generator(print_format) {
		return !print_format.custom_format && !print_format.raw_printing;
	}

	preview() {
		this.toggle_style_picker();
		let print_format = this.get_print_format();
		if (this.renders_via_generator(print_format)) {
			this.print_wrapper.find(".print-preview-wrapper").hide();
			this.print_wrapper.find(".preview-beta-wrapper").show();
			this.preview_beta();
			return;
		}

		this.print_wrapper.find(".preview-beta-wrapper").hide();
		this.print_wrapper.find(".print-preview-wrapper").show();

		this.get_print_html((out) => {
			if (!out.html) {
				out.html = this.get_no_preview_html();
			}

			const $print_format = this.print_wrapper.find("iframe");
			this.$print_format_body = $print_format.contents();
			this.setup_print_format_dom(out, $print_format);

			const print_height = $print_format.get(0).offsetHeight;
			const $message = this.wrapper.find(".page-break-message");

			const print_height_inches = frappe.dom.pixel_to_inches(print_height);
			// if contents are large enough, indicate that it will get printed on multiple pages
			// Maximum height for an A4 document is 11.69 inches
			if (print_height_inches > 11.69) {
				$message.text(__("This may get printed on multiple pages"));
			} else {
				$message.text("");
			}
		});
	}

	preview_beta() {
		const iframe = this.print_wrapper.find(".preview-beta-wrapper iframe");
		let params = new URLSearchParams({
			doctype: this.frm.doc.doctype,
			name: this.frm.doc.name,
			print_format: this.selected_format(),
		});
		if (this.lang_code) {
			params.append("_lang", this.lang_code);
		}
		let letterhead = this.get_letterhead();
		if (letterhead) {
			params.append("letterhead", letterhead);
		}
		const settings = this.get_print_settings_param();
		if (Object.keys(settings).length) {
			params.append("settings", JSON.stringify(settings));
		}
		if (this.get_print_style()) {
			params.append("style", this.get_print_style());
		}
		iframe.off("load").on("load", () => this.on_preview_load(iframe.get(0)));
		iframe.prop("src", `/printpreview?${params.toString()}`);
		iframe.css("height", "calc(100vh - var(--page-head-height) - var(--navbar-height))");
	}

	setup_print_format_dom(out, $print_format) {
		this.print_wrapper.find(".print-format-skeleton").remove();
		let base_url = frappe.urllib.get_base_url();
		let print_css = frappe.assets.bundled_asset(
			"print.bundle.css",
			frappe.utils.is_rtl(this.lang_code)
		);
		this.$print_format_body
			.find("html")
			.attr("dir", frappe.utils.is_rtl(this.lang_code) ? "rtl" : "ltr");
		this.$print_format_body.find("html").attr("lang", this.lang_code);
		this.$print_format_body.find("head").html(
			`<link href="${base_url}${print_css}" rel="stylesheet">
			<style type="text/css">${out.style}</style>`
		);

		this.$print_format_body
			.find("body")
			.html(`<div class="print-format print-format-preview">${out.html}</div>`);
		const iframeDoc = this.$print_format_body[0];
		iframeDoc.querySelectorAll("svg[data-barcode-value]").forEach((el) => {
			const get_options = frappe.ui.form.ControlBarcode.prototype.get_options.bind({
				df: { options: el.dataset.options },
			});
			JsBarcode(el, el.dataset.barcodeValue, get_options(el.dataset.barcodeValue));
			el.setAttribute("width", "100%");
		});
		this.show_footer();

		this.$print_format_body.find(".print-format").css({
			display: "flex",
			flexDirection: "column",
		});

		this.$print_format_body.find(".page-break").css({
			display: "flex",
			"flex-direction": "column",
			flex: "1",
		});

		setTimeout(() => {
			$print_format.height(this.$print_format_body.find(".print-format").outerHeight());

			// Add keyboard shortcut to refresh the print preview inside the iframe,
			// since Frappe's default shortcuts don't work within iframes.

			const iframe = this.print_wrapper.find("iframe.print-format-container")[0];
			const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;

			// Add a flag on the iframe document to avoid duplicate listeners
			if (!iframeDoc._refreshShortcutAttached) {
				iframeDoc.addEventListener("keydown", (e) => {
					if (e.shiftKey && e.key.toLowerCase() === "r") {
						e.preventDefault();
						this.refresh_print_format();
					}
				});

				// Set the flag so this block won't run again
				iframeDoc._refreshShortcutAttached = true;
			}
		}, 500);
	}

	hide() {
		if (this.frm.setup_done && this.frm.page.current_view_name === "print") {
			this.frm.page.set_view(
				this.frm.page.previous_view_name === "print"
					? "main"
					: this.frm.page.previous_view_name || "main"
			);
		}
	}

	go_to_form_view() {
		frappe.route_options = {
			frm: this,
		};
		frappe.set_route("Form", this.frm.doctype, this.frm.docname);
	}

	show_footer() {
		// footer is hidden by default as reqd by pdf generation
		// simple hack to show it in print preview

		this.$print_format_body.find("#footer-html").attr(
			"style",
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

		if (cint(me.print_settings.enable_print_server)) {
			if (localStorage.getItem("network_printer")) {
				me.print_by_server();
			} else {
				me.network_printer_setting_dialog(() => me.print_by_server());
			}
		} else if (me.get_mapped_printer().length === 1) {
			// printer is already mapped in localstorage (applies for both raw and pdf )
			if (me.is_raw_printing()) {
				me.get_raw_commands(function (out) {
					frappe.ui.form
						.qz_connect()
						.then(function () {
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
							"Please remove the printer mapping in Printer Settings and try again."
						),
						indicator: "info",
					},
					14
				);
				//Note: need to solve "Error: Cannot parse (FILE)<URL> as a PDF file" to enable qz pdf printing.
			}
		} else if (me.is_raw_printing()) {
			// printer not mapped in localstorage and the current print format is raw printing
			frappe.show_alert(
				{
					message: __("Printer mapping not set."),
					subtitle: __(
						"Please set a printer mapping for this print format in the Printer Settings"
					),
					indicator: "warning",
				},
				14
			);
			me.printer_setting_dialog();
		} else {
			me.render_page("/printview?", true);
		}
	}

	print_by_server() {
		let me = this;
		if (localStorage.getItem("network_printer")) {
			frappe.call({
				method: "frappe.utils.print_format.print_by_server",
				args: {
					doctype: me.frm.doc.doctype,
					name: me.frm.doc.name,
					printer_setting: localStorage.getItem("network_printer"),
					print_format: me.selected_format(),
					no_letterhead: me.with_letterhead(),
					letterhead: me.get_letterhead(),
					style: me.get_print_style() || undefined,
					settings: JSON.stringify(me.get_print_settings_param()),
				},
				callback: function () {},
			});
		}
	}
	network_printer_setting_dialog(callback) {
		frappe.call({
			method: "frappe.printing.doctype.network_printer_settings.network_printer_settings.get_network_printer_settings",
			callback: function (r) {
				if (r.message) {
					let d = new frappe.ui.Dialog({
						title: __("Select Network Printer"),
						fields: [
							{
								label: "Printer",
								fieldname: "printer",
								fieldtype: "Select",
								reqd: 1,
								options: r.message,
							},
						],
						primary_action: function () {
							localStorage.setItem("network_printer", d.get_values().printer);
							if (typeof callback == "function") {
								callback();
							}
							d.hide();
						},
						primary_action_label: __("Select"),
					});
					d.show();
				}
			},
		});
	}
	render_pdf() {
		let print_format = this.get_print_format();
		if (this.renders_via_generator(print_format)) {
			let params = new URLSearchParams({
				doctype: this.frm.doc.doctype,
				name: this.frm.doc.name,
				letterhead: this.get_letterhead(),
				// "Standard" when the selector is cleared: an omitted format means
				// the doctype's default, the same as everywhere else in printing
				print_format: this.selected_format(),
			});
			const settings = this.get_print_settings_param();
			if (Object.keys(settings).length) {
				params.append("settings", JSON.stringify(settings));
			}
			if (this.lang_code) {
				params.append("_lang", this.lang_code);
			}
			if (this.get_print_style()) {
				params.append("style", this.get_print_style());
			}
			let w = window.open(
				`/api/method/frappe.utils.print_format_generator.download_pdf?${params}`
			);
			if (!w) {
				frappe.msgprint(__("Please enable pop-ups"));
				return;
			}
		} else {
			this.render_page(
				"/api/method/frappe.utils.print_format.download_pdf?",
				false,
				print_format?.pdf_generator
			);
		}
	}
	render_page(method, printit = false, pdf_generator) {
		let w = window.open(
			frappe.urllib.get_full_url(
				method +
					"doctype=" +
					encodeURIComponent(this.frm.doc.doctype) +
					"&name=" +
					encodeURIComponent(this.frm.doc.name) +
					(printit ? "&trigger_print=1" : "") +
					"&format=" +
					encodeURIComponent(this.selected_format()) +
					"&no_letterhead=" +
					(this.with_letterhead() ? "0" : "1") +
					"&letterhead=" +
					encodeURIComponent(this.get_letterhead()) +
					"&settings=" +
					encodeURIComponent(JSON.stringify(this.get_print_settings_param())) +
					(this.lang_code ? "&_lang=" + this.lang_code : "") +
					(this.get_print_style()
						? "&style=" + encodeURIComponent(this.get_print_style())
						: "") +
					"&pdf_generator=" +
					encodeURIComponent(pdf_generator || "chrome")
			)
		);
		if (!w) {
			frappe.msgprint(__("Please enable pop-ups"));
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
			method: "frappe.www.printview.get_html_and_style",
			args: {
				doc: this.frm.doc,
				print_format: this.selected_format(),
				no_letterhead: !this.with_letterhead() ? 1 : 0,
				letterhead: this.get_letterhead(),
				settings: this.additional_settings,
				_lang: this.lang_code,
			},
			callback: function (r) {
				if (!r.exc) {
					callback(r.message);
				}
			},
		});
	}

	get_letterhead() {
		return this.letterhead_selector.val() || __("No Letterhead");
	}

	get_no_preview_html() {
		return `<div class="text-muted text-center" style="font-size: 1.2em;">
			${__("No Preview Available")}
		</div>`;
	}

	get_raw_commands(callback) {
		// fetches rendered raw commands from the server for the current print format.
		frappe.call({
			method: "frappe.www.printview.get_rendered_raw_commands",
			args: {
				doc: this.frm.doc,
				print_format: this.selected_format(),
				_lang: this.lang_code,
			},
			callback: function (r) {
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
			return JSON.parse(localStorage.print_format_printer_map);
		} catch (e) {
			return {};
		}
	}

	set_default_print_format() {
		const default_format =
			this.frm._layout_print_format || this.frm.meta.default_print_format || "";
		this.set_print_format_value(default_format);
	}

	// apps like Print Designer replace setup_sidebar and only provide
	// print_format_selector, not the whole control
	set_print_format_value(value) {
		if (this.print_format_field) {
			this.print_format_field.set_input(value);
		} else {
			this.print_format_selector.val(value);
		}
	}

	selected_format() {
		return this.print_format_selector.val() || "Standard";
	}

	is_raw_printing(format) {
		return this.get_print_format(format).raw_printing === 1;
	}

	get_print_format(format) {
		let print_format = {};
		if (!format) {
			format = this.selected_format();
		}

		if (locals[":Print Format"] && locals[":Print Format"][format]) {
			print_format = locals[":Print Format"][format];
		}

		return print_format;
	}

	with_letterhead() {
		return cint(this.get_letterhead() !== __("No Letterhead"));
	}

	set_style(style) {
		frappe.dom.set_style(style || frappe.boot.print_css, "print-style");
	}

	printer_setting_dialog() {
		// dialog for the Printer Settings
		this.print_format_printer_map = this.get_print_format_printer_map();
		this.data = this.print_format_printer_map[this.frm.doctype] || [];
		this.printer_list = [];
		frappe.ui.form.qz_get_printer_list().then((data) => {
			this.printer_list = data;
			const dialog = new frappe.ui.Dialog({
				title: __("Printer Settings"),
				fields: [
					{
						fieldtype: "Section Break",
					},
					{
						fieldname: "printer_mapping",
						fieldtype: "Table",
						label: __("Printer Mapping"),
						in_place_edit: true,
						data: this.data,
						get_data: () => {
							return this.data;
						},
						fields: [
							{
								fieldtype: "Select",
								fieldname: "print_format",
								default: 0,
								options: frappe.meta.get_print_formats(this.frm.doctype),
								read_only: 0,
								in_list_view: 1,
								label: __("Print Format"),
							},
							{
								fieldtype: "Select",
								fieldname: "printer",
								default: 0,
								options: this.printer_list,
								read_only: 0,
								in_list_view: 1,
								label: __("Printer"),
							},
						],
					},
				],
				primary_action: () => {
					let printer_mapping = dialog.get_values()["printer_mapping"];
					if (printer_mapping && printer_mapping.length) {
						let print_format_list = printer_mapping.map((a) => a.print_format);
						let has_duplicate = print_format_list.some(
							(item, idx) => print_format_list.indexOf(item) != idx
						);
						if (has_duplicate)
							frappe.throw(
								__(
									"Cannot have multiple printers mapped to a single print format."
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
				primary_action_label: __("Save"),
			});
			dialog.show();
			if (!(this.printer_list && this.printer_list.length)) {
				frappe.throw(__("No Printer is Available."));
			}
		});
	}
};
