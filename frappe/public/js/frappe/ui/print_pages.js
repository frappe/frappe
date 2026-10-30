frappe.ui.PrintPages = class PrintPages {
	static find_breaks({ sheet, breaks }) {
		const style = getComputedStyle(sheet);
		const pad_top = parseFloat(style.paddingTop);
		const height = parseFloat(style.minHeight) - pad_top - parseFloat(style.paddingBottom);
		if (!(height > 0)) return null;

		const rect = sheet.getBoundingClientRect();
		const scale = sheet.currentCSSZoom
			? 1 / sheet.currentCSSZoom
			: sheet.offsetHeight / (rect.height || 1);
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
				const widths = (part) =>
					[...(part?.rows || [])].map((row) =>
						[...row.cells].map((cell) => cell.getBoundingClientRect().width * scale)
					);
				atoms.push([
					y(head.top),
					y(table.tBodies[0].rows[0].getBoundingClientRect().bottom),
				]);
				return {
					table,
					top: y(head.bottom),
					bottom: y(r.bottom),
					height: head.height * scale,
					foot: band(table.tFoot),
					left: (r.left - rect.left) * scale - parseFloat(style.paddingLeft),
					width: r.width * scale,
					cells: { tHead: widths(table.tHead), tFoot: widths(table.tFoot) },
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
			const open = (at) => tables.filter((t) => t.top < at - 0.5 && t.bottom > at + 0.5);
			let limit = fits ? total : start + room - foot;
			if (!fits) limit -= Math.max(0, ...open(limit).map((t) => t.foot));
			if (limit <= start + 1) limit = start + height;
			const end =
				forced.find((at) => at > start + 1 && at < Math.min(limit, total - 1)) ??
				(fits ? total : fit(start, limit));
			pages.push({ start, end, repeat, close: open(end).filter((t) => t.foot) });
			start = end;
		}
		return {
			pages,
			frame,
			width: rect.width * scale,
			height: sheet.clientHeight - pad_top - parseFloat(style.paddingBottom),
		};
	}

	static paginate({ sheet, breaks }) {
		const doc = sheet.ownerDocument;
		const layout = this.find_breaks({ sheet, breaks });
		if (!layout || layout.pages.length < 2) return [];

		const style = getComputedStyle(sheet);
		const layers = ["::before", "::after"]
			.map((pseudo) => getComputedStyle(sheet, pseudo))
			.filter((layer) => layer.content !== "none" && layer.backgroundImage !== "none");
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
		const table_part = (t, part) => {
			const table = t.table.cloneNode(false);
			const head = table.appendChild(t.table[part].cloneNode(true));
			[...head.rows].forEach((row, r) =>
				[...row.cells].forEach(
					(cell, c) => (cell.style.width = `${t.cells[part][r][c]}px`)
				)
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
		const flows = new Map();
		const pages = layout.pages.map(({ start, end, repeat, close }, i) => {
			const page = doc.createElement("div");
			page.className = `${sheet.className} preview-page`;
			Object.assign(page.style, {
				boxSizing: "border-box",
				width: `${layout.width}px`,
				height: style.minHeight,
				minHeight: style.minHeight,
				padding: style.padding,
				background: style.backgroundColor,
				boxShadow: style.boxShadow,
				borderRadius: style.borderRadius,
				overflow: "hidden",
				position: "relative",
				isolation: "isolate",
			});
			layers.forEach((layer) => {
				const el = page.appendChild(doc.createElement("div"));
				Object.assign(el.style, {
					position: "absolute",
					inset: "0",
					zIndex: "-1",
					pointerEvents: "none",
					opacity: layer.opacity,
					backgroundImage: layer.backgroundImage,
					backgroundPosition: layer.backgroundPosition,
					backgroundSize: layer.backgroundSize,
					backgroundRepeat: layer.backgroundRepeat,
					backgroundColor: layer.backgroundColor,
				});
			});
			if (i && layout.frame?.tHead) page.append(band(layout.frame.tHead));

			repeat.forEach((t) => page.append(table_part(t, "tHead")));

			const slice = page.appendChild(doc.createElement("div"));
			Object.assign(slice.style, { height: `${end - start}px`, overflow: "hidden" });
			const flow = slice.appendChild(doc.createElement("div"));
			Object.assign(flow.style, {
				display: style.display === "flex" ? "flex" : "flow-root",
				flexDirection: style.flexDirection,
				minHeight: `${layout.height}px`,
				marginTop: `${-start}px`,
			});
			flows.set(page, flow);
			close.forEach((t) => page.append(table_part(t, "tFoot")));

			if (i < layout.pages.length - 1 && layout.frame?.tFoot) {
				page.append(band(layout.frame.tFoot));
			}
			return container.appendChild(page);
		});

		const fill = ({ target, isIntersecting }) => {
			const flow = flows.get(target);
			if (!isIntersecting) return flow.replaceChildren();
			if (flow.childNodes.length) return;
			content.forEach((node) => flow.append(node.cloneNode(true)));
			flow.querySelectorAll("script").forEach((el) => el.remove());
			flow.querySelectorAll(":scope > .preview-source").forEach((el) =>
				el.classList.remove("preview-source")
			);
		};
		const observer = new doc.defaultView.IntersectionObserver(
			(entries) => entries.forEach(fill),
			{ root: doc, rootMargin: "100% 0px" }
		);
		pages.forEach((page) => observer.observe(page));

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
				body.preview-paginated::before,
				body.preview-paginated::after { display: none; }
				.preview-pages .preview-page { margin: 0 auto 24px; }
			}
			@media print { .preview-pages { display: none; } }
		`;
		return pages;
	}
};
