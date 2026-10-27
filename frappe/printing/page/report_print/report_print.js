const PAPER_SIZES = {
	a3: [297, 420],
	a4: [210, 297],
	a5: [148, 210],
	a6: [105, 148],
	b4: [250, 353],
	b5: [176, 250],
	executive: [184.15, 266.7],
	ledger: [279.4, 431.8],
	legal: [215.9, 355.6],
	letter: [215.9, 279.4],
	tabloid: [279.4, 431.8],
};

const FOOTER_STYLE = `<style>
	@media print {
		.print-format:has(> #footer-html) {
			display: flex;
			flex-direction: column;
			min-height: 100vh;
		}
		#footer-html {
			margin-top: auto;
		}
	}
</style>`;

const PREVIEW_STYLE = `<style>
	@media screen {
		:root {
			margin: 0;
			background-color: var(--gray-200);
		}
		:root body {
			margin: 0;
			background: none;
		}
		.print-format-gutter {
			background: none;
			padding: calc(var(--spacing) * 8);
		}
		.print-format {
			border-radius: var(--radius-sm);
			box-shadow: var(--shadow-md);
		}
	}
</style>`;

frappe.pages["report-print"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({ parent: wrapper });

	const print_view = new frappe.views.ReportPrintView(wrapper);

	$(wrapper).on("hide", () => frappe.app?.sidebar?.unfold_after_leaving_page());
	$(wrapper).on("show", () => {
		frappe.app?.sidebar?.fold_for_page();
		print_view.show(frappe.get_route().slice(1).join("/"));
	});
};

frappe.views.ReportPrintView = class ReportPrintView {
	constructor(wrapper) {
		this.page = wrapper.page;
		this.render_count = 0;
		this.make();
	}

	show(report_name) {
		const print_format = frappe.route_options?.print_format;
		frappe.route_options = null;

		this.report = frappe.query_report;
		if (
			this.report?.report_name !== report_name ||
			!this.report.data?.length ||
			!frappe.model.can_print(this.report.report_doc?.ref_doctype)
		) {
			frappe.route_flags.replace_route = true;
			frappe.set_route("query-report", report_name);
			return;
		}

		this.page.set_title(__(report_name));
		this.page.set_breadcrumbs([
			{
				label: __(report_name),
				href: `/desk/query-report/${encodeURIComponent(report_name)}`,
			},
			{ label: __("Print") },
		]);
		this.setup_controls(print_format).then(() => this.refresh());
	}

	make() {
		this.page.main.html(`
			<div class="preview-beta-wrapper report-print-preview">
				<iframe width="100%" height="0" frameBorder="0"></iframe>
			</div>
		`);
		this.$preview = this.page.main.find(".preview-beta-wrapper");
		this.$iframe = this.$preview.find("iframe");
		this.preview_bar = new frappe.ui.PrintPreviewBar({
			parent: this.$preview,
			get_metrics: (doc) => this.get_page_metrics(doc),
		});

		this.page.set_primary_action(__("Print"), () => this.print(), "printer");
		this.page.add_button(__("Full Page"), () => this.open_full_page(), { icon: "fullscreen" });
		this.page.add_button(__("PDF"), () => this.download_pdf(), { icon: "file" });
		this.page.add_button(__("Refresh"), () => this.refresh(), { icon: "refresh-cw" });
		this.page.add_button(
			__("Report"),
			() => frappe.set_route("query-report", this.report.report_name),
			{ icon: "sheet" }
		);
		this.page.add_menu_item(__("Print Settings"), () =>
			frappe.set_route("Form", "Print Settings")
		);

		frappe.ui.keys.add_shortcut({
			shortcut: "ctrl+p",
			ignore_inputs: true,
			action: () => this.print(),
			page: this.page,
			description: __("Print report"),
			condition: () => !!this.html,
		});

		this.sidebar = this.page.sidebar.addClass("print-preview-sidebar");
	}

	async setup_controls(print_format) {
		this.sidebar.empty();
		const formats = await frappe.db.get_list("Print Format", {
			filters: { print_format_for: "Report", report: this.report.report_name, disabled: 0 },
			order_by: "name asc",
			limit: 100,
		});
		const names = formats.map((format) => format.name);

		this.sidebar.append(`<div class="print-sidebar-heading">${__("Format")}</div>`);
		this.format_field = this.add_control({
			fieldtype: "Select",
			fieldname: "print_format",
			label: __("Print Format"),
			options: ["", ...names],
			placeholder: __("None"),
			default:
				[print_format, this.report.report_doc.default_print_format].find((name) =>
					names.includes(name)
				) || "",
			change: () => this.refresh(),
		});
		this.letter_head_field = this.add_control({
			fieldtype: "Link",
			fieldname: "letter_head",
			label: __("Letter Head"),
			options: "Letter Head",
			placeholder: __("None"),
			default: this.default_letter_head(),
			get_query: () => ({ filters: { letter_head_for: "Report", disabled: 0 } }),
			change: () => this.refresh(),
		});

		const $page = $(`<div class="print-page-settings">
			<div class="print-sidebar-heading">${__("Page")}</div>
		</div>`).appendTo(this.sidebar);
		this.orientation_set_by_user = false;
		this.orientation_field = this.add_control(
			{
				fieldtype: "Select",
				fieldname: "orientation",
				label: __("Orientation"),
				options: [
					{ label: __("Portrait"), value: "Portrait" },
					{ label: __("Landscape"), value: "Landscape" },
				],
				change: () => {
					this.orientation_set_by_user = true;
					this.refresh();
				},
			},
			$page
		);
		this.include_filters_field = this.add_control(
			{
				fieldtype: "Check",
				fieldname: "include_filters",
				label: __("Include filters"),
				default: 1,
				change: () => this.refresh(),
			},
			$page
		);
		this.pick_columns_field = this.add_control(
			{
				fieldtype: "Check",
				fieldname: "pick_columns",
				label: __("Pick columns"),
				change: () => this.refresh(),
			},
			$page
		);

		this.$columns = $(`<div class="print-page-settings report-print-columns"></div>`).appendTo(
			this.sidebar
		);
		this.columns_field = this.add_control(
			{
				fieldtype: "MultiCheck",
				fieldname: "columns",
				select_all: true,
				sort_options: false,
				columns: 1,
				options: this.report.get_visible_columns().map((df) => ({
					label: __(df.label, null, df.parent),
					value: df.fieldname,
					checked: 1,
				})),
				on_change: () => this.refresh(),
			},
			this.$columns
		);
		this.columns_field.$checkbox_area.css("padding", "");
	}

	add_control(df, parent) {
		const field = frappe.ui.form.make_control({
			df,
			parent: parent || this.sidebar,
			render_input: 1,
		});
		if (df.default != null) field.set_input(df.default);
		return field;
	}

	default_letter_head() {
		const company = frappe.defaults.get_default("company");
		return (
			this.report.report_doc.default_letter_head ||
			locals[":Company"]?.[company]?.default_letter_head_report ||
			frappe.defaults.get_default("letter_head_report") ||
			""
		);
	}

	get_print_settings() {
		const letter_head = this.letter_head_field.get_value();
		const print_format = this.format_field.get_value() || null;
		const columns = this.columns_field.get_checked_options();
		const pick_columns = !print_format && this.pick_columns_field.get_value();

		return {
			...locals[":Print Settings"]?.["Print Settings"],
			print_format,
			orientation: this.orientation_set_by_user
				? this.orientation_field.get_value()
				: "Landscape",
			with_letter_head: letter_head ? 1 : 0,
			letter_head_name: letter_head || null,
			letter_head: letter_head ? frappe.boot.letter_heads?.[letter_head] : null,
			include_filters: this.include_filters_field.get_value(),
			columns:
				pick_columns && columns.length < this.report.get_visible_columns().length
					? columns
					: null,
		};
	}

	async refresh() {
		const count = ++this.render_count;
		const print_settings = this.get_print_settings();
		this.html = null;
		this.$preview.addClass("is-rendering");
		const out = await this.report.get_print_html(print_settings);
		if (count !== this.render_count) return;
		if (!out) return this.$preview.removeClass("is-rendering");

		const page_size = this.get_page_size(out.html);
		if (page_size.orientation && !this.orientation_set_by_user) {
			print_settings.orientation = page_size.orientation;
		}
		this.orientation_field.set_input(print_settings.orientation);
		const size = this.get_size_for(page_size, print_settings.orientation);
		const [width, height] = this.get_paper(page_size, print_settings);
		this.print_settings = print_settings;
		this.format = out.format;
		this.html = out.html.replace("</body>", `<style>@page { size: ${size}; }</style></body>`);
		this.include_filters_field.toggle(out.format.type !== "jinja");
		this.pick_columns_field.toggle(!print_settings.print_format);
		this.$columns.toggle(
			!print_settings.print_format && !!this.pick_columns_field.get_value()
		);
		this.$iframe.off("load").on("load", () => this.on_preview_load());
		this.$iframe.prop(
			"srcdoc",
			this.html.replace(
				"</head>",
				`${PREVIEW_STYLE}<style>@media screen { .print-format, .print-format.landscape { width: ${width}; max-width: none; min-height: ${height}; } }</style></head>`
			)
		);
	}

	get_page_size(html) {
		const value = html.match(/@page\s*\{[^}]*\bsize\s*:\s*([^;}]+)/i)?.[1] || "";
		const tokens = value.trim().toLowerCase().split(/\s+/).filter(Boolean);
		const keyword = tokens.find((token) => token === "portrait" || token === "landscape");
		const lengths = tokens.filter((token) => /^[\d.]+[a-z]+$/.test(token));
		const [width, height] = lengths.map(parseFloat);
		const orientation =
			keyword || (lengths.length === 2 && (width > height ? "landscape" : "portrait"));
		return {
			orientation: orientation && frappe.utils.to_title_case(orientation),
			name: tokens.find(
				(token) => /^[a-z]/.test(token) && token !== keyword && token !== "auto"
			),
			lengths,
		};
	}

	get_size_for(page_size, orientation) {
		const { name, lengths } = page_size;
		if (lengths.length !== 2)
			return [name, orientation.toLowerCase()].filter(Boolean).join(" ");

		const [width, height] = lengths;
		const is_landscape = parseFloat(width) > parseFloat(height);
		return is_landscape === (orientation === "Landscape")
			? `${width} ${height}`
			: `${height} ${width}`;
	}

	get_paper(page_size, print_settings) {
		let [width, height] = page_size.lengths;
		if (!height) {
			const custom = !page_size.name && print_settings.pdf_page_size === "Custom";
			const name = page_size.name || (print_settings.pdf_page_size || "a4").toLowerCase();
			const mm =
				custom && print_settings.pdf_page_width && print_settings.pdf_page_height
					? [print_settings.pdf_page_width, print_settings.pdf_page_height]
					: PAPER_SIZES[name] || PAPER_SIZES.a4;
			[width, height] = mm.map((value) => `${value}mm`);
		}
		const is_landscape = parseFloat(width) > parseFloat(height);
		return is_landscape === (print_settings.orientation === "Landscape")
			? [width, height]
			: [height, width];
	}

	show_footer(doc) {
		const footer = doc.getElementById("footer-html");
		if (!footer) return;
		footer.classList.remove("visible-pdf");
		doc.head.insertAdjacentHTML("beforeend", FOOTER_STYLE);
	}

	on_preview_load() {
		const frame = this.$iframe.get(0);
		const doc = frame.contentDocument;
		if (!doc?.body) return;
		const landscape = this.print_settings.orientation === "Landscape";
		doc.querySelector(".print-format")?.classList.toggle("landscape", landscape);
		this.show_footer(doc);
		this.$preview.removeClass("is-rendering");
		this.preview_bar.attach(frame, { fit: true });
		doc.addEventListener("keydown", (e) => {
			if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "p") {
				e.preventDefault();
				this.print();
			}
		});
	}

	get_page_metrics(doc) {
		const sheet = doc.querySelector(".print-format");
		if (!sheet) return null;
		return {
			top: sheet.offsetTop,
			width: sheet.offsetWidth,
			starts: frappe.ui.PrintPreviewBar.measure_pages({
				page: sheet,
				page_height: parseFloat(getComputedStyle(sheet).minHeight),
				breaks: ".page-break:not(:last-child)",
			}),
		};
	}

	print() {
		if (!this.html || this.$preview.hasClass("is-rendering")) return;
		this.report.make_access_log("Print", "HTML");
		const win = this.$iframe.get(0).contentWindow;
		win.focus();
		win.print();
	}

	open_full_page() {
		if (!this.html) return;
		const win = window.open();
		if (!win) return frappe.msgprint(__("Please enable pop-ups in your browser"));
		this.report.make_access_log("Print", "HTML");
		win.document.write(this.html);
		this.show_footer(win.document);
		win.document.close();
	}

	download_pdf() {
		if (!this.html) return;
		if (
			!this.report.tree_report &&
			(this.format.type === "jinja" ||
				(this.format.type === "grid" && !this.report.report_settings.formatter))
		) {
			return this.report.download_pdf_from_server(this.print_settings, this.format);
		}

		this.report.make_access_log("Print", "PDF");
		frappe.render_pdf(this.html, {
			...this.print_settings,
			report_name: this.report.get_pdf_filename(),
		});
	}
};
