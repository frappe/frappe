// View A draws the layers and their folders; view B the matrix of which layer uses which.
/* global DATA, ORDER, state, inLoop, layer, box, isBreak, esc, short, layerName, layerClass */
function drawLayers() {
	const view = document.getElementById("view");
	const W = Math.max(900, view.clientWidth - 40);
	const LABEL = 200,
		SIDE = 170,
		ROW = 54,
		GAP = 12,
		TOP = 8;
	const rows = ORDER.filter((id) => id !== "build");
	const pos = new Map();
	const avail = W - LABEL - SIDE - 24;
	rows.forEach((id, r) => {
		const bs = DATA.boxes.filter((b) => b.layer === id).sort((a, b) => b.lines - a.lines);
		const minW = 34,
			total = bs.reduce((n, b) => n + b.lines, 0);
		const free = avail - bs.length * (minW + 3);
		let x = LABEL;
		for (const b of bs) {
			const w = minW + (total ? (b.lines / total) * free : 0);
			pos.set(b.id, { x, y: TOP + r * (ROW + GAP), w, h: ROW });
			x += w + 3;
		}
	});
	const buildBoxes = DATA.boxes.filter((b) => b.layer === "build");
	const bx = W - SIDE + 10,
		bTop = TOP + rows.indexOf("6") * (ROW + GAP);
	buildBoxes.forEach((b, i) =>
		pos.set(b.id, { x: bx, y: bTop + i * (ROW + GAP), w: SIDE - 20, h: ROW })
	);
	const H = TOP + rows.length * (ROW + GAP) + 10;

	const sel = state.selected?.kind === "box" ? state.selected.id : null;
	const linked = sel
		? new Set(
				DATA.edges
					.filter((e) => e.from === sel || e.to === sel)
					.flatMap((e) => [e.from, e.to])
		  )
		: null;
	const shown = DATA.edges.filter((e) => {
		if (sel) return e.from === sel || e.to === sel;
		if (state.showAll) return true;
		return isBreak(e);
	});

	let svg = `<svg width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg">`;
	rows.forEach((id, r) => {
		const l = layer(id),
			y = TOP + r * (ROW + GAP);
		const bs = DATA.boxes.filter((b) => b.layer === id);
		const lines = bs.reduce((n, b) => n + b.lines, 0);
		const folders = bs.length === 1 ? __("1 folder") : __("{0} folders", [bs.length]);
		svg += `<g class="layerlabel ${layerClass(id)}" data-select="layer" data-id="${esc(
			id
		)}"><rect class="bg" x="0" y="${y}" width="${LABEL - 8}" height="${ROW}" rx="6"/>
			<rect class="swatch" x="0" y="${y}" width="5" height="${ROW}" rx="2"/>
			<text class="title" x="12" y="${y + 20}">${esc(layerName(id))}</text>
			<text class="muted" x="12" y="${y + 38}">${
			bs.length
				? __("{0}, {1} lines, {2} concepts", [
						folders,
						lines.toLocaleString(),
						l.concepts.length,
				  ])
				: __("{0} concepts, not in the graph", [l.concepts.length])
		}</text></g>`;
		if (!bs.length)
			svg += `<rect class="empty" x="${LABEL}" y="${y}" width="${avail}" height="${ROW}" rx="4"/>
			<text class="faint" x="${LABEL + 10}" y="${y + 31}">${__(
				"App folders and Client Script rows. They reach the desk only through the import list and the page object."
			)}</text>`;
	});
	svg += `<text x="${bx}" y="${bTop - 8}" class="layerlabel title">${__(
		"The build (beside)"
	)}</text>`;

	const edgeSvg = shown
		.map((e) => {
			const a = pos.get(e.from),
				b = pos.get(e.to);
			if (!a || !b) return "";
			const up = b.y < a.y,
				same = a.y === b.y;
			const x1 = a.x + a.w / 2,
				x2 = b.x + b.w / 2;
			const y1 = same ? a.y : up ? a.y : a.y + a.h,
				y2 = same ? b.y : up ? b.y + b.h : b.y;
			const bend = same ? -30 : (y2 - y1) / 2;
			const d = `M${x1},${y1} C${x1},${y1 + bend} ${x2},${
				y2 - (same ? -bend : bend)
			} ${x2},${y2}`;
			const tone = ["break", "known", "callback"].includes(e.status)
				? e.status
				: sel
				? e.from === sel
					? "out"
					: "in"
				: "plain";
			const width = isBreak(e) ? 2.2 : Math.min(4, 0.8 + Math.log2(e.count + 1) * 0.5);
			const op = isBreak(e) || sel ? 0.9 : 0.25;
			return `<path class="edge ${tone}" d="${d}" stroke-width="${width}" opacity="${op}"/>
			<path class="edge hit" d="${d}" data-select="edge" data-id="${esc(e.id)}"><title>${__(
				"{0} to {1}: {2} ({3})",
				[esc(short(box(e.from).folder)), esc(short(box(e.to).folder)), e.count, e.status]
			)}</title></path>`;
		})
		.join("");

	for (const b of DATA.boxes) {
		const p = pos.get(b.id);
		if (!p) continue;
		const cls = [
			"box",
			layerClass(b.layer),
			sel === b.id ? "sel" : "",
			linked && !linked.has(b.id) ? "dim" : "",
			state.showLoops && inLoop.has(b.folder) ? "loop" : "",
		].join(" ");
		const name =
			b.files.length === 1
				? b.files[0].path.split("/").pop()
				: short(b.folder).split("/").pop();
		const fits = p.w > 52;
		svg += `<g class="${cls}" data-select="box" data-id="${esc(b.id)}"><title>${__(
			"{0}: {1} files, {2} lines",
			[esc(b.folder), b.files.length, b.lines]
		)}</title>
			<rect x="${p.x}" y="${p.y}" width="${p.w}" height="${p.h}" rx="4" opacity="${
			0.55 + Math.min(0.45, b.lines / 6000)
		}"/>
			${
				fits
					? `<text class="name" x="${p.x + 5}" y="${p.y + 20}">${esc(
							name.length * 6.2 > p.w - 8
								? name.slice(0, Math.floor((p.w - 8) / 6.2)) + "…"
								: name
					  )}</text>
			<text x="${p.x + 5}" y="${p.y + 37}" opacity=".85">${b.lines.toLocaleString()}</text>`
					: ""
			}</g>`;
	}
	svg += edgeSvg + `</svg>`;

	view.innerHTML =
		`<div class="legend">
		<span><i class="edge break"></i>${__("new break (CI fails)")}</span>
		<span><i class="edge known"></i>${__("known break (has a ticket)")}</span>
		<span><i class="edge callback"></i>${__("callback")}</span>
		<label><input type="checkbox" ${
			state.showAll ? "checked" : ""
		} onchange="state.showAll=this.checked;drawLayers()"> ${__("show all {0} edges", [
			DATA.edges.length,
		])}</label>
		<label><input type="checkbox" ${
			state.showLoops ? "checked" : ""
		} onchange="state.showLoops=this.checked;drawLayers()"> ${__(
			"mark folders in loops"
		)}</label>
		${
			sel
				? `<a href="#" onclick="state.selected=null;document.getElementById('panel').innerHTML=idleDetail();drawLayers();return false">${__(
						"clear selection"
				  )}</a>`
				: ""
		}
		<span>${__("Box width: share of its layer's lines.")}</span></div>` + svg;
}

function drawMatrix() {
	const ids = ORDER.filter((id) => id !== "9");
	const sum = {};
	for (const e of DATA.edges) {
		const k = box(e.from).layer + ">" + box(e.to).layer;
		sum[k] ??= { n: 0, bad: 0 };
		sum[k].n += e.count;
		if (isBreak(e)) sum[k].bad += e.count;
	}
	let html = `<p class="muted">${__(
		"Rows use columns. A green cell is a use the layer file allows; a grey cell is one it does not. A number is the count of file pairs; red means the code does what the layer file forbids. Customization is left out: it is not in the import graph."
	)}</p>
		<table class="matrix"><tr><th class="row">${__("uses →")}</th>${ids
		.map(
			(c) =>
				`<th title="${esc(layerName(c))}">${
					c === "main" ? "main" : c === "build" ? "build" : c
				}</th>`
		)
		.join("")}</tr>`;
	for (const r of ids) {
		html += `<tr><th class="row"><a href="#" data-select="layer" data-id="${esc(r)}">${esc(
			layerName(r)
		)}</a></th>`;
		for (const c of ids) {
			const s = sum[r + ">" + c];
			const may = layer(r).mayUse.includes(c);
			const cls = r === c ? "self" : s?.bad ? "bad" : may ? "may" : "no";
			html += `<td class="${cls} ${s ? "has" : ""}" ${
				s ? `data-select="cell" data-id="${esc(`${r}>${c}`)}"` : ""
			}>${s ? s.n : ""}</td>`;
		}
		html += `</tr>`;
	}
	html += `</table>
		<h3 class="loops">${__("Folder loops")}</h3>
		<p class="muted">${__(
			"Groups of folders that import each other. The layer file cannot show these; the loop check does."
		)}</p>
		<table class="matrix">${DATA.loops
			.map(
				(c) =>
					`<tr><td class="row">${__("{0} folders", [c.length])}</td><td class="row">${c
						.map((f) => `<code>${esc(short(f))}</code>`)
						.join(" ")}</td></tr>`
			)
			.join("")}</table>`;
	document.getElementById("view").innerHTML = html;
}
