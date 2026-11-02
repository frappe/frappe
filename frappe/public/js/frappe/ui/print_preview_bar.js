frappe.ui.PrintPreviewBar = class PrintPreviewBar {
	static measure_pages({ page, page_height, breaks, repeated = 0 }) {
		const rect = page.getBoundingClientRect();
		const scale = page.offsetHeight / (rect.height || 1);
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
		page.querySelectorAll(breaks).forEach((el) => {
			const end = (el.getBoundingClientRect().bottom - rect.top) * scale;
			start = fill(start, end);
			if (end < page.offsetHeight - 1) {
				start = end;
				starts.push(start);
			}
		});
		fill(start, page.offsetHeight);
		return starts;
	}

	constructor({ parent, get_metrics }) {
		this.get_metrics = get_metrics;
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

	attach(frame, { fit = false } = {}) {
		const doc = frame.contentDocument;
		this.frame = frame;
		this.zoom_style = doc.head.appendChild(doc.createElement("style"));
		doc.addEventListener("scroll", () => this.update_page_label());
		if (fit && !this.zoom_set_by_user) this.fit(1);
		this.apply_zoom();
	}

	metrics() {
		const doc = this.frame?.contentDocument;
		const metrics = doc?.body && this.get_metrics(doc);
		return metrics ? { ...metrics, doc } : null;
	}

	update_page_label() {
		const m = this.metrics();
		if (!m) return;
		const el = m.doc.scrollingElement;
		const pages = m.starts.length;
		const at_end = el.scrollTop > 0 && el.scrollTop + el.clientHeight >= el.scrollHeight - 2;
		const middle = (el.scrollTop + el.clientHeight / 2) / this.zoom - m.top;
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
			top: (m.top + m.starts[page - 1]) * this.zoom,
			behavior: "smooth",
		});
	}

	set_zoom(zoom) {
		this.zoom = Math.min(2, Math.max(0.5, Math.round(zoom * 10) / 10));
		this.apply_zoom();
	}

	apply_zoom() {
		if (this.zoom_style) {
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
