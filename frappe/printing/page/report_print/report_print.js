const PRINT_VIEW_OPTIONS = ["print_format", "letter_head", "orientation"];

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
			width: 8.3in;
			border-radius: var(--radius-sm);
			box-shadow: var(--shadow-md);
		}
		.print-format.landscape {
			width: 11.69in;
			min-height: 8.27in;
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
		this.zoom = 1;
		this.zoom_set_by_user = false;
		this.current_page = 1;
		this.render_count = 0;
		this.px_per_inch = 1 / frappe.dom.pixel_to_inches(1);
		this.make();
	}

	show(report_name) {
		const options = frappe.route_options || {};
		frappe.route_options = null;

		const filters = Object.fromEntries(
			Object.entries(options).filter(([key]) => !PRINT_VIEW_OPTIONS.includes(key))
		);
		const view_options = Object.fromEntries(
			Object.entries(options).filter(([key]) => PRINT_VIEW_OPTIONS.includes(key))
		);

		const report = frappe.query_report;
		const reload = report?.report_name !== report_name || !this.filters_match(report, filters);
		if (reload) {
			frappe.flags.pending_report_print = { report_name, route_options: view_options };
		}
		if (reload || !report.data?.length) {
			this.html = null;
			frappe.route_flags.replace_route = true;
			frappe.set_route("query-report", report_name, filters);
			return;
		}

		this.report = report;
		this.set_breadcrumbs(report_name);
		this.setup_controls(view_options).then(() => this.refresh());
	}

	filters_match(report, filters) {
		const current = report.get_filter_values();
		const text = (value) =>
			Array.isArray(value) ? JSON.stringify(value) : String(value ?? "");
		return Object.entries(filters).every(([key, value]) => text(current[key]) === text(value));
	}

	update_url() {
		if (frappe.get_route()[0] !== "report-print") return;
		const url = new URL(this.report.get_url_with_filters());
		const view_options = {
			print_format: this.print_settings.print_format,
			letter_head: this.print_settings.letter_head_name,
			orientation: this.orientation_set_by_user && this.print_settings.orientation,
		};
		for (const [key, value] of Object.entries(view_options)) {
			if (value) url.searchParams.set(key, value);
		}
		window.history.replaceState(null, null, url);
	}

	set_breadcrumbs(report_name) {
		this.page.set_title(__(report_name));
		this.page.set_breadcrumbs([
			{
				label: __(report_name),
				href: `/desk/query-report/${encodeURIComponent(report_name)}`,
			},
			{ label: __("Print") },
		]);
	}

	make() {
		this.page.main.html(`
			<div class="preview-beta-wrapper report-print-preview">
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
		`);
		this.$preview = this.page.main.find(".preview-beta-wrapper");
		this.$iframe = this.$preview.find("iframe");
		this.preview_bar = this.$preview.find(".print-preview-bar");
		this.preview_bar.on("click", "[data-action]", (e) => {
			const action = e.currentTarget.dataset.action;
			if (action === "next-page") return this.go_to_page(this.current_page + 1);
			if (action === "prev-page") return this.go_to_page(this.current_page - 1);

			this.zoom_set_by_user = true;
			if (action === "zoom-in") this.set_zoom(this.zoom + 0.1);
			else if (action === "zoom-out") this.set_zoom(this.zoom - 0.1);
			else if (action === "fit") this.fit_zoom();
		});

		this.page.set_primary_action(__("Print"), () => this.print(), "printer");
		this.page.add_action_icon("sheet", () => this.back_to_report(), "", __("Back to Report"));
		this.page.add_action_icon("download", () => this.download_pdf(), "", __("Download PDF"));

		frappe.ui.keys.add_shortcut({
			shortcut: "ctrl+p",
			action: () => this.print(),
			page: this.page,
			description: __("Print report"),
			condition: () => !!this.html,
		});

		this.sidebar = this.page.sidebar.addClass("print-preview-sidebar");
	}

	async setup_controls(view_options) {
		this.sidebar.empty();
		const formats = await this.get_print_formats();

		this.add_heading(__("Format"));
		this.format_field = this.add_control({
			fieldtype: "Select",
			fieldname: "print_format",
			label: __("Print Format"),
			options: [{ label: __("Standard"), value: "" }, ...formats],
			default: this.pick(
				view_options.print_format,
				formats,
				this.report.report_doc.default_print_format
			),
			change: () => {
				if (!this.orientation_set_by_user) {
					this.orientation_field.set_input(this.default_orientation);
				}
				this.refresh();
			},
		});
		this.letter_head_field = this.add_control({
			fieldtype: "Link",
			fieldname: "letter_head",
			label: __("Letter Head"),
			options: "Letter Head",
			placeholder: __("None"),
			default: view_options.letter_head ?? this.default_letter_head(),
			get_query: () => ({ filters: { letter_head_for: "Report", disabled: 0 } }),
			change: () => this.refresh(),
		});

		const $page_settings = $(`<div class="print-page-settings"></div>`).appendTo(this.sidebar);
		this.add_heading(__("Page"), $page_settings);
		this.orientation_set_by_user = !!view_options.orientation;
		this.default_orientation =
			view_options.orientation ||
			(this.report.columns.length > 10 ? "Landscape" : "Portrait");
		this.orientation_field = this.add_control(
			{
				fieldtype: "Select",
				fieldname: "orientation",
				label: __("Orientation"),
				options: [
					{ label: __("Portrait"), value: "Portrait" },
					{ label: __("Landscape"), value: "Landscape" },
				],
				default: this.default_orientation,
				change: () => {
					this.orientation_set_by_user = true;
					this.refresh();
				},
			},
			$page_settings
		);
		this.include_filters_field = this.add_control(
			{
				fieldtype: "Check",
				fieldname: "include_filters",
				label: __("Include filters"),
				default: 1,
				change: () => this.refresh(),
			},
			$page_settings
		);

		this.$columns = $(`<div class="print-page-settings"></div>`).appendTo(this.sidebar);
		this.add_heading(__("Columns"), this.$columns);
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
	}

	add_heading(label, parent) {
		return $(`<div class="print-sidebar-heading">${label}</div>`).appendTo(
			parent || this.sidebar
		);
	}

	add_control(df, parent) {
		if (df.fieldtype === "Select") {
			df.input_class = "btn btn-default btn-sm text-left";
		}
		const field = frappe.ui.form.make_control({
			df,
			parent: parent || this.sidebar,
			render_input: 1,
		});
		if (df.default != null) {
			field.set_input(df.default);
		}
		return field;
	}

	pick(requested, formats, fallback) {
		if (formats.includes(requested)) return requested;
		return formats.includes(fallback) ? fallback : "";
	}

	async get_print_formats() {
		const formats = await frappe.db.get_list("Print Format", {
			filters: {
				print_format_for: "Report",
				report: this.report.report_name,
				disabled: 0,
			},
			order_by: "name asc",
			limit: 100,
		});
		return (formats || []).map((format) => format.name);
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
		const print_settings = { ...locals[":Print Settings"]?.["Print Settings"] };
		const letter_head_name = this.letter_head_field.get_value();
		const print_format = this.format_field.get_value() || null;
		const columns = this.columns_field.get_checked_options();
		const all_columns = this.report.get_visible_columns().length;

		return Object.assign(print_settings, {
			print_format,
			orientation: this.orientation_field.get_value(),
			with_letter_head: letter_head_name ? 1 : 0,
			letter_head_name: letter_head_name || null,
			letter_head: letter_head_name ? frappe.boot.letter_heads?.[letter_head_name] : null,
			include_filters: this.include_filters_field.get_value(),
			columns: !print_format && columns.length < all_columns ? columns : null,
		});
	}

	async refresh() {
		const count = ++this.render_count;
		const print_settings = this.get_print_settings();
		this.$preview.addClass("is-rendering");
		const out = await this.report.get_print_html(print_settings);
		if (count !== this.render_count) return;
		if (!out) {
			this.$preview.removeClass("is-rendering");
			return;
		}

		this.print_settings = print_settings;
		this.html = out.html;
		this.toggle_settings(out.format);
		this.update_url();
		this.$iframe.off("load").on("load", () => this.on_preview_load());
		this.$iframe.prop("srcdoc", this.html.replace("</head>", `${PREVIEW_STYLE}</head>`));
		this.$iframe.css("height", "calc(100vh - var(--page-head-height))");
	}

	toggle_settings(format) {
		const is_jinja = format.type === "jinja";
		this.include_filters_field.toggle(!is_jinja);
		this.$columns.toggle(!this.format_field.get_value());
	}

	on_preview_load() {
		this.preview_frame = this.$iframe.get(0);
		const doc = this.preview_frame.contentDocument;
		if (!doc?.body) return;
		this.$preview.removeClass("is-rendering");
		this.sync_orientation();
		if (this.zoom_set_by_user) this.apply_zoom();
		else this.fit_zoom(1);
		doc.addEventListener("scroll", () => this.update_page_label());
		doc.addEventListener("keydown", (e) => {
			if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "p") {
				e.preventDefault();
				this.print();
			}
		});
		this.update_page_label();
	}

	page_metrics() {
		const doc = this.preview_frame?.contentDocument;
		const sheet = doc?.querySelector(".print-format");
		if (!sheet) return null;
		const landscape = parseFloat(getComputedStyle(sheet).maxWidth) > 9 * this.px_per_inch;
		const page_height = (landscape ? 8.27 : 11.69) * this.px_per_inch;
		const pages = Math.max(1, Math.ceil((sheet.offsetHeight - 1) / page_height));
		return { doc, sheet, landscape, page_height, pages };
	}

	sync_orientation() {
		const m = this.page_metrics();
		if (!m || this.orientation_set_by_user) return;
		const orientation = m.landscape ? "Landscape" : "Portrait";
		this.print_settings.orientation = orientation;
		this.orientation_field.set_input(orientation);
	}

	update_page_label() {
		const m = this.page_metrics();
		if (!m) return;
		const el = m.doc.scrollingElement;
		const at_end = el.scrollTop > 0 && el.scrollTop + el.clientHeight >= el.scrollHeight - 2;
		const middle = (el.scrollTop + el.clientHeight / 2) / this.zoom - m.sheet.offsetTop;
		this.current_page = at_end
			? m.pages
			: Math.min(m.pages, Math.max(1, Math.floor(middle / m.page_height) + 1));
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
			top: (m.sheet.offsetTop + (page - 1) * m.page_height) * this.zoom,
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

	fit_zoom(max_zoom = 2) {
		const m = this.page_metrics();
		if (!m) return;
		const fit = (this.preview_frame.clientWidth - 96) / m.sheet.offsetWidth;
		this.set_zoom(Math.min(max_zoom, Math.floor(fit * 10) / 10));
	}

	print() {
		if (!this.html) return;
		this.report.make_access_log("Print", "HTML");
		const win = this.preview_frame?.contentWindow;
		win?.focus();
		win?.print();
	}

	download_pdf() {
		if (!this.html) return;
		this.report.make_access_log("Print", "PDF");
		frappe.render_pdf(this.html, {
			...this.print_settings,
			report_name: this.report.get_pdf_filename(),
		});
	}

	back_to_report() {
		frappe.set_route("query-report", this.report.report_name);
	}
};
