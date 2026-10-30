frappe.ui.PrintPreviewBar = class PrintPreviewBar {
	static find_breaks({ sheet, breaks }) {
		const style = getComputedStyle(sheet);
		const pad_top = parseFloat(style.paddingTop);
		const height = parseFloat(style.minHeight) - pad_top - parseFloat(style.paddingBottom);
		if (!(height > 0)) return null;

		const rect = sheet.getBoundingClientRect();
		const scale = sheet.offsetHeight / (rect.height || 1);
		const y = (top) => (top - rect.top) * scale - pad_top;
		const atoms = [];
		const add = (r) => r.height > 0.5 && atoms.push([y(r.top), y(r.bottom)]);
		const forced = [];
		const avoid_after = [];

		const range = sheet.ownerDocument.createRange();
		const walker = sheet.ownerDocument.createTreeWalker(sheet, NodeFilter.SHOW_TEXT);
		while (walker.nextNode()) {
			if (!walker.currentNode.data.trim()) continue;
			range.selectNodeContents(walker.currentNode);
			[...range.getClientRects()].forEach(add);
		}
		const is_page = (value) => ["page", "always", "left", "right"].includes(value);
		sheet.querySelectorAll("*").forEach((el) => {
			const el_style = getComputedStyle(el);
			if (el_style.display === "none") return;
			const r = el.getBoundingClientRect();
			if (
				el.matches(
					"img, svg, canvas, video, iframe, input, textarea, select, tr:not(.print-repeating-frame > * > tr)"
				) ||
				el_style.breakInside.startsWith("avoid")
			) {
				add(r);
			}
			if (is_page(el_style.breakBefore)) forced.push(y(r.top));
			if (is_page(el_style.breakAfter) || (breaks && el.matches(breaks))) {
				forced.push(y(r.bottom));
			}
			if (el_style.breakAfter.startsWith("avoid")) avoid_after.push(r);
		});
		atoms.sort((a, b) => a[0] - b[0]);
		avoid_after.forEach((r) => {
			const next = atoms.find(([top]) => top >= y(r.bottom) - 0.5);
			if (next) atoms.push([y(r.top), next[1]]);
		});
		forced.sort((a, b) => a - b);

		const frame = sheet.querySelector(":scope > .print-repeating-frame");
		const band = (part) => (part ? part.getBoundingClientRect().height * scale : 0);
		const head = band(frame?.tHead);
		const foot = band(frame?.tFoot);
		const tables = [...sheet.querySelectorAll("table")]
			.filter(
				(table) =>
					table !== frame && table.tHead?.offsetHeight && table.tBodies[0]?.rows[0]
			)
			.map((table) => {
				const r = table.getBoundingClientRect();
				const head = table.tHead.getBoundingClientRect();
				atoms.push([
					y(head.top),
					y(table.tBodies[0].rows[0].getBoundingClientRect().bottom),
				]);
				return {
					table,
					top: y(head.bottom),
					bottom: y(r.bottom),
					height: head.height * scale,
					left: (r.left - rect.left) * scale - parseFloat(style.paddingLeft),
					width: r.width * scale,
					cells: [...table.tHead.rows].map((row) =>
						[...row.cells].map((cell) => cell.getBoundingClientRect().width * scale)
					),
				};
			});
		const total = Math.max(
			sheet.clientHeight - pad_top - parseFloat(style.paddingBottom),
			...[...sheet.children].map((el) => y(el.getBoundingClientRect().bottom))
		);

		const fit = (start, limit) => {
			const room = limit - start;
			const moves = (top, bottom) =>
				bottom - top <= room ||
				!atoms.some(([t, b]) => t < top - 0.5 && b >= bottom - 0.5 && b - t > room);
			let end = limit;
			for (let moved = true; moved; ) {
				moved = false;
				for (const [top, bottom] of atoms) {
					if (
						top > start + 1 &&
						top < end - 0.5 &&
						bottom > end + 0.5 &&
						moves(top, bottom)
					) {
						end = top;
						moved = true;
					}
				}
			}
			return end > start + 1 ? end : limit;
		};

		const pages = [];
		let start = 0;
		while (start < total - 1 && pages.length < 500) {
			const repeat = pages.length
				? tables.filter((t) => t.top < start - 0.5 && t.bottom > start + 0.5)
				: [];
			const room =
				height - (pages.length ? head : 0) - repeat.reduce((sum, t) => sum + t.height, 0);
			const fits = total - start <= room;
			let limit = fits ? total : start + room - foot;
			if (limit <= start + 1) limit = start + height;
			const end =
				forced.find((at) => at > start + 1 && at < Math.min(limit, total - 1)) ??
				(fits ? total : fit(start, limit));
			pages.push({ start, end, repeat });
			start = end;
		}
		return {
			pages,
			frame,
			height: sheet.clientHeight - pad_top - parseFloat(style.paddingBottom),
		};
	}

	static paginate({ sheet, breaks }) {
		const doc = sheet.ownerDocument;
		const layout = this.find_breaks({ sheet, breaks });
		if (!layout || layout.pages.length < 2) return [];

		const style = getComputedStyle(sheet);
		const content = [...sheet.childNodes].filter(
			(node) => !(node.nodeType === Node.ELEMENT_NODE && node.matches("script"))
		);
		const band = (part) => {
			const table = layout.frame.cloneNode(false);
			table.append(part.cloneNode(true));
			return table;
		};
		const container = doc.createElement("div");
		container.className = "preview-pages";
		const reset = {
			margin: "0",
			padding: "0",
			border: "0",
			background: "none",
			boxShadow: "none",
			display: "block",
			height: "auto",
			minHeight: "0",
		};
		const table_head = (t) => {
			const table = t.table.cloneNode(false);
			const head = table.appendChild(t.table.tHead.cloneNode(true));
			[...head.rows].forEach((row, r) =>
				[...row.cells].forEach((cell, c) => (cell.style.width = `${t.cells[r][c]}px`))
			);
			Object.assign(table.style, {
				width: `${t.width}px`,
				tableLayout: "fixed",
				margin: `0 0 0 ${t.left}px`,
			});
			let node = table;
			for (let el = t.table.parentElement; el && el !== sheet; el = el.parentElement) {
				const parent = el.cloneNode(false);
				Object.assign(parent.style, reset);
				parent.append(node);
				node = parent;
			}
			return node;
		};
		const pages = layout.pages.map(({ start, end, repeat }, i) => {
			const page = doc.createElement("div");
			page.className = `${sheet.className} preview-page`;
			Object.assign(page.style, {
				boxSizing: "border-box",
				width: `${sheet.offsetWidth}px`,
				height: style.minHeight,
				minHeight: style.minHeight,
				padding: style.padding,
				background: style.backgroundColor,
				boxShadow: style.boxShadow,
				borderRadius: style.borderRadius,
				overflow: "hidden",
			});
			if (i && layout.frame?.tHead) page.append(band(layout.frame.tHead));

			repeat.forEach((t) => page.append(table_head(t)));

			const slice = page.appendChild(doc.createElement("div"));
			Object.assign(slice.style, { height: `${end - start}px`, overflow: "hidden" });
			const flow = slice.appendChild(doc.createElement("div"));
			Object.assign(flow.style, {
				display: style.display === "flex" ? "flex" : "flow-root",
				flexDirection: style.flexDirection,
				minHeight: `${layout.height}px`,
				marginTop: `${-start}px`,
			});
			content.forEach((node) => flow.append(node.cloneNode(true)));
			flow.querySelectorAll("script").forEach((el) => el.remove());

			if (i < layout.pages.length - 1 && layout.frame?.tFoot) {
				page.append(band(layout.frame.tFoot));
			}
			return container.appendChild(page);
		});

		if (sheet === doc.body) {
			content.forEach(
				(node) =>
					node.nodeType === Node.ELEMENT_NODE && node.classList.add("preview-source")
			);
			doc.body.classList.add("preview-paginated");
			doc.body.append(container);
		} else {
			sheet.classList.add("preview-source");
			sheet.after(container);
		}
		doc.head.appendChild(doc.createElement("style")).textContent = `
			@media screen {
				.preview-source { display: none; }
				body.preview-paginated {
					background: none;
					box-shadow: none;
					padding: 0;
					min-height: 0;
				}
				.preview-pages .preview-page { margin: 0 auto 24px; }
			}
			@media print { .preview-pages { display: none; } }
		`;
		return pages;
	}

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
		if (fit && !this.zoom_set_by_user) this.fit(1);
		this.apply_zoom();

		await doc.fonts?.ready;
		await Promise.all(
			[...doc.images]
				.filter((img) => !img.complete)
				.map((img) => new Promise((resolve) => (img.onload = img.onerror = resolve)))
		);
		if (frame.contentDocument !== doc) return;
		const sheet = this.get_sheet(doc);
		if (sheet?.sheet) this.pages = frappe.ui.PrintPreviewBar.paginate(sheet);
		this.update_page_label();
	}

	metrics() {
		const doc = this.frame?.contentDocument;
		if (!doc?.body) return null;
		if (this.pages?.length && this.pages[0].ownerDocument === doc) {
			const top = this.pages[0].offsetTop;
			return {
				doc,
				top,
				width: this.pages[0].offsetWidth,
				starts: this.pages.map((page) => page.offsetTop - top),
			};
		}
		const sheet = this.get_sheet(doc)?.sheet;
		return sheet ? { doc, top: sheet.offsetTop, width: sheet.offsetWidth, starts: [0] } : null;
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
