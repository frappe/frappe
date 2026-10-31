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
		const is_page = (value) => ["page", "always", "left", "right"].includes(value);
		const visit = (parent) => {
			for (const node of parent.childNodes) {
				if (node.nodeType === Node.TEXT_NODE) {
					if (!node.data.trim()) continue;
					range.selectNodeContents(node);
					[...range.getClientRects()].forEach(add);
					continue;
				}
				if (node.nodeType !== Node.ELEMENT_NODE) continue;
				const el_style = getComputedStyle(node);
				if (el_style.display === "none") continue;
				const r = node.getBoundingClientRect();
				const row = node.matches("tr:not(.print-repeating-frame > * > tr)");
				if (
					row ||
					node.matches("img, svg, canvas, video, iframe, input, textarea, select") ||
					el_style.breakInside.startsWith("avoid")
				) {
					add(r);
				}
				if (is_page(el_style.breakBefore)) forced.push(y(r.top));
				if (is_page(el_style.breakAfter) || (breaks && node.matches(breaks))) {
					forced.push(y(r.bottom));
				}
				if (el_style.breakAfter.startsWith("avoid")) avoid_after.push(r);
				if (!row || r.height * scale > height) visit(node);
			}
		};
		visit(sheet);
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
			y,
			scale,
			width: rect.width * scale,
			height: sheet.clientHeight - pad_top - parseFloat(style.paddingBottom),
		};
	}

	static measure(sheet, { pages, y, scale }) {
		const cuts = pages.slice(1).map((page) => page.start);
		const geometry = new Map();
		const columns = new Map();
		const stacked = new Set();
		const pruned = new Map();
		const column_widths = (table) => {
			const rows = [...table.rows];
			const span = (row) => [...row.cells].reduce((sum, cell) => sum + cell.colSpan, 0);
			const count = Math.max(0, ...rows.map(span));
			const row = rows.find((r) => r.cells.length === count);
			if (!row) return null;
			const rects = [...row.cells].map((cell) => cell.getBoundingClientRect());
			if (getComputedStyle(table).borderCollapse !== "collapse") {
				return rects.map((r) => r.width * scale);
			}
			const edges = [...rects.map((r) => r.left), rects.at(-1).right];
			return rects.map((r, i) => (edges[i + 1] - r.left) * scale);
		};
		const prunable = (el, kids) => {
			if (el.localName === "table") {
				const widths = column_widths(el);
				if (widths) {
					columns.set(el, { widths, width: el.getBoundingClientRect().width * scale });
				}
				return !!widths;
			}
			if (el.matches("thead, tbody, tfoot, tr")) {
				return columns.has(el.closest("table"));
			}
			return (
				[...el.childNodes].every(
					(node) => node.nodeType !== Node.TEXT_NODE || !node.data.trim()
				) &&
				kids.every(([, kid_style]) => {
					const display = kid_style.display;
					return !display.startsWith("inline") && display !== "contents";
				})
			);
		};
		const visit = (el) => {
			const kids = [...el.children]
				.filter((kid) => !kid.matches("script"))
				.map((kid) => [kid, getComputedStyle(kid)]);
			if (!prunable(el, kids)) return;
			pruned.set(
				el,
				kids
					.map(([kid]) => kid)
					.filter((kid) => !(columns.has(el) && kid.matches("colgroup, col")))
			);
			const style = getComputedStyle(el);
			const column = style.display.endsWith("flex")
				? style.flexDirection === "column" && style.flexWrap === "nowrap"
				: ["block", "flow-root"].includes(style.display);
			if (
				el.matches("thead, tbody, tfoot") ||
				(column &&
					kids.every(
						([, kid_style]) =>
							kid_style.float === "none" &&
							!["absolute", "fixed"].includes(kid_style.position) &&
							kid_style.display !== "list-item"
					))
			) {
				stacked.add(el);
			}
			kids.forEach(([kid, kid_style]) => {
				if (kid_style.display === "none") return;
				const r = kid.getBoundingClientRect();
				const g = {
					top: y(r.top),
					bottom: y(r.bottom),
					width: r.width * scale,
					height: r.height * scale,
					margin_top: kid_style.marginTop,
					margin_bottom: kid_style.marginBottom,
				};
				geometry.set(kid, g);
				if (cuts.some((at) => g.top < at - 0.5 && g.bottom > at + 0.5)) visit(kid);
			});
		};
		visit(sheet);
		return { geometry, columns, stacked, pruned };
	}

	static slice(sheet, { geometry, columns, stacked, pruned }, start, end) {
		const doc = sheet.ownerDocument;
		const box = (node) => {
			const g = geometry.get(node);
			const el = node.cloneNode(false);
			Object.assign(el.style, {
				boxSizing: "border-box",
				width: `${g.width}px`,
				height: `${g.height}px`,
				minHeight: "0",
				marginTop: g.margin_top,
				marginBottom: g.margin_bottom,
				flex: "none",
			});
			return el;
		};
		const filler = (parent, run) => {
			const first = geometry.get(run[0]);
			const height = `${geometry.get(run.at(-1)).bottom - first.top}px`;
			let el;
			if (parent.matches("thead, tbody, tfoot")) {
				el = doc.createElement("tr");
				const cell = el.appendChild(doc.createElement("td"));
				cell.colSpan = 1000;
				Object.assign(cell.style, { height, padding: "0", border: "0" });
			} else {
				el = doc.createElement("div");
				Object.assign(el.style, {
					height,
					marginTop: first.margin_top,
					marginBottom: geometry.get(run.at(-1)).margin_bottom,
					flex: "none",
				});
			}
			if (run.length % 2 === 0) {
				const twin = el.cloneNode(false);
				twin.style.display = "none";
				return [el, twin];
			}
			return [el];
		};
		const copy = (el) => {
			const clone = el.cloneNode(false);
			const { widths, width } = columns.get(el) || {};
			if (widths) {
				Object.assign(clone.style, { width: `${width}px`, tableLayout: "fixed" });
				const group = clone.appendChild(doc.createElement("colgroup"));
				widths.forEach((col) => {
					group.appendChild(doc.createElement("col")).style.width = `${col}px`;
				});
			}
			clone.append(...children(el));
			return clone;
		};
		const children = (parent) => {
			const out = [];
			const section = parent.matches("thead, tbody, tfoot");
			const row = parent.localName === "tr";
			let run = [];
			const flush = () => {
				if (!run.length) return;
				if (section) out.push(...filler(parent, run));
				else if (!stacked.has(parent) || run.length < 3) out.push(...run.map(box));
				else out.push(box(run[0]), ...filler(parent, run.slice(1, -1)), box(run.at(-1)));
				run = [];
			};
			for (const node of pruned.get(parent)) {
				const g = geometry.get(node);
				const inside = !g || (g.top >= start - 0.5 && g.bottom <= end + 0.5);
				const outside = g && (g.bottom <= start + 0.5 || g.top >= end - 0.5);
				if (outside && !row) {
					run.push(node);
					continue;
				}
				flush();
				out.push(inside || !pruned.has(node) ? node.cloneNode(true) : copy(node));
			}
			flush();
			return out;
		};
		return pruned.has(sheet)
			? children(sheet)
			: [...sheet.childNodes]
					.filter(
						(node) => !(node.nodeType === Node.ELEMENT_NODE && node.matches("script"))
					)
					.map((node) => node.cloneNode(true));
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
		const measured = this.measure(sheet, layout);
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
				overflow: "clip",
				position: "relative",
				isolation: "isolate",
				contentVisibility: "auto",
				containIntrinsicSize: `${layout.width}px ${style.minHeight}`,
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
			Object.assign(slice.style, {
				display: "flow-root",
				height: `${end - start}px`,
				overflow: "clip",
			});
			const flow = slice.appendChild(doc.createElement("div"));
			Object.assign(flow.style, {
				display: style.display === "flex" ? "flex" : "flow-root",
				flexDirection: style.flexDirection,
				minHeight: `${layout.height}px`,
				marginTop: `${-start}px`,
			});
			flow.append(...this.slice(sheet, measured, start, end));
			flow.querySelectorAll("script").forEach((el) => el.remove());
			close.forEach((t) => page.append(table_part(t, "tFoot")));

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
				body.preview-paginated::before,
				body.preview-paginated::after { display: none; }
				.preview-pages .preview-page { margin: 0 auto 24px; }
			}
			@media print { .preview-pages { display: none; } }
		`;
		return pages;
	}
};
