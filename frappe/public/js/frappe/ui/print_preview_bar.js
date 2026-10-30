frappe.ui.PrintPreviewBar = class PrintPreviewBar {
	constructor({ parent, get_sheet }) {
		this.get_sheet = get_sheet;
		this.zoom = 1;
		this.$wrapper = $(`
			<div class="print-preview-bar">
				${this.icon_button("prev-page", "chevron-up", __("Previous page"))}
				<span class="print-preview-bar-label page-label"></span>
				${this.icon_button("next-page", "chevron-down", __("Next page"))}
				<span class="print-preview-bar-divider"></span>
				${this.icon_button("zoom-out", "minus", __("Zoom out"))}
				<span class="print-preview-bar-label zoom-label"></span>
				${this.icon_button("zoom-in", "plus", __("Zoom in"))}
				<button class="es-button" data-variant="ghost" data-size="sm" data-action="fit">${__(
					"Fit"
				)}</button>
			</div>
		`).appendTo(parent);
		this.$wrapper.on("click", "[data-action]", (e) => {
			const action = e.currentTarget.dataset.action;
			if (action === "next-page") return this.go_to_page(this.current_page + 1);
			if (action === "prev-page") return this.go_to_page(this.current_page - 1);

			this.zoom_set_by_user = true;
			if (action === "zoom-in") this.set_zoom(this.zoom + 0.1);
			else if (action === "zoom-out") this.set_zoom(this.zoom - 0.1);
			else if (action === "fit") this.fit();
		});
	}

	icon_button(action, icon, label) {
		return `<button class="es-button" data-variant="ghost" data-size="sm" data-icon-button="true" data-action="${action}" aria-label="${label}">${frappe.utils.icon(
			icon,
			"sm"
		)}</button>`;
	}

	async attach(frame, { fit = false } = {}) {
		const doc = frame.contentDocument;
		this.frame = frame;
		this.pages = [];
		this.zoom_style = doc.head.appendChild(doc.createElement("style"));
		doc.addEventListener("scroll", () => this.update_page_label());
		doc.defaultView.addEventListener("resize", () => this.apply_zoom());
		if (fit && !this.zoom_set_by_user) this.fit(1);
		this.apply_zoom();

		await doc.fonts?.ready;
		await Promise.all(
			[...doc.images]
				.filter((img) => !img.complete)
				.map((img) => new Promise((resolve) => (img.onload = img.onerror = resolve)))
		);
		await frappe.require("print_pages.bundle.js");
		if (frame.contentDocument !== doc) return;
		const sheet = this.get_sheet(doc);
		if (!sheet?.sheet) return;
		this.zoom_style.textContent = "";
		this.pages = frappe.ui.PrintPages.paginate(sheet);
		this.apply_zoom();
	}

	metrics() {
		const doc = this.frame?.contentDocument;
		if (!doc?.body) return null;
		if (this.pages?.length && this.pages[0].ownerDocument === doc) {
			const scroll = doc.scrollingElement.scrollTop;
			return {
				doc,
				width: this.pages[0].offsetWidth,
				starts: this.pages.map((page) => page.getBoundingClientRect().top + scroll),
			};
		}
		const sheet = this.get_sheet(doc)?.sheet;
		return sheet ? { doc, width: sheet.offsetWidth, starts: [0] } : null;
	}

	update_page_label() {
		const m = this.metrics();
		if (!m) return;
		const el = m.doc.scrollingElement;
		const pages = m.starts.length;
		const at_end = el.scrollTop > 0 && el.scrollTop + el.clientHeight >= el.scrollHeight - 2;
		const middle = el.scrollTop + el.clientHeight / 2;
		this.current_page = at_end
			? pages
			: Math.max(1, m.starts.filter((start) => start <= middle).length);
		this.$wrapper.find(".page-label").text(__("Page {0} of {1}", [this.current_page, pages]));
		this.$wrapper.find("[data-action=prev-page]").prop("disabled", this.current_page <= 1);
		this.$wrapper.find("[data-action=next-page]").prop("disabled", this.current_page >= pages);
	}

	go_to_page(page) {
		const m = this.metrics();
		if (!m) return;
		page = Math.min(m.starts.length, Math.max(1, page));
		m.doc.scrollingElement.scrollTo({
			top: m.starts[page - 1],
			behavior: "smooth",
		});
	}

	set_zoom(zoom) {
		this.zoom = Math.min(2, Math.max(0.5, Math.round(zoom * 10) / 10));
		this.apply_zoom();
	}

	apply_zoom() {
		const container = this.pages?.[0]?.parentElement;
		if (container) {
			const width = parseFloat(this.pages[0].style.width);
			const height = container.offsetHeight;
			const left =
				container.getBoundingClientRect().left -
				parseFloat(getComputedStyle(container).marginLeft);
			const frame_width = container.ownerDocument.documentElement.clientWidth;
			const margin_left = Math.max(-left, (frame_width - width * this.zoom) / 2 - left);
			this.zoom_style.textContent = `@media screen { .preview-pages {
				width: ${width}px;
				margin: 0 0 ${height * (this.zoom - 1)}px ${margin_left}px;
				transform: scale(${this.zoom});
				transform-origin: 0 0;
			} }`;
		} else if (this.zoom_style) {
			this.zoom_style.textContent = `@media screen { :root { zoom: ${this.zoom}; } }`;
		}
		this.$wrapper.find(".zoom-label").text(`${Math.round(this.zoom * 100)}%`);
		this.update_page_label();
	}

	fit(max_zoom = 2) {
		const m = this.metrics();
		if (!m) return;
		const fit = (this.frame.clientWidth - 96) / m.width;
		this.set_zoom(Math.min(max_zoom, Math.floor(fit * 10) / 10));
	}
};
