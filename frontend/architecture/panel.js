// The details panel: what one click on a layer, a folder, a line or a card shows.
/* global DATA, INK, VIEWS, ORDER, state, current, drawLayers, esc, md, short, layer, box, isBreak, layerName, archLink, statusPill, fileLink */
function select(kind, id) {
	state.selected = { kind, id };
	const panel = document.getElementById("panel");
	panel.innerHTML = {
		layer: layerDetail,
		box: boxDetail,
		edge: edgeDetail,
		cell: cellDetail,
		ext: extDetail,
	}[kind](id);
	panel.scrollTop = 0;
	if (current().key === "A") drawLayers();
}
function idleDetail() {
	return `<h2>${__("Click anything")}</h2>
		<p class="muted">${__(
			"A layer name, a folder, a line between folders, a matrix cell, a flow step or a card. The details show here."
		)}</p>
		<h3>${__("Read the colours")}</h3>
		<p>${__(
			"A {0} line or cell is an import that the layer file does not allow. Dashed red is a known break: the layer file lists it with the ticket that removes it. Solid red is new: CI fails on it.",
			[`<b style="color:${INK.red}">${__("red")}</b>`]
		)}</p>
		<p>${__(
			"An orange dashed outline marks a folder inside a loop, where folders import each other."
		)}</p>
		<h3>${__("Where the data comes from")}</h3>
		<p>${__(
			"Built on each request from the code (the import graph), {0} (which layer may use which) and {1} (the concepts and the flows). The ways to change the desk come from the same file.",
			[
				"<code>frontend/architecture/layers.json</code>",
				`<code>${esc(DATA.architecture)}</code>`,
			]
		)}</p>`;
}
function layerDetail(id) {
	const l = layer(id);
	const boxes = DATA.boxes.filter((b) => b.layer === id);
	const out = DATA.edges.filter((e) => box(e.from).layer === id && box(e.to).layer !== id);
	const inn = DATA.edges.filter((e) => box(e.to).layer === id && box(e.from).layer !== id);
	const byLayer = (edges, end) => {
		const m = {};
		for (const e of edges) {
			const k = box(e[end]).layer;
			m[k] ??= { n: 0, bad: 0 };
			m[k].n += e.count;
			if (isBreak(e)) m[k].bad += e.count;
		}
		return Object.entries(m)
			.sort((a, b) => ORDER.indexOf(a[0]) - ORDER.indexOf(b[0]))
			.map(
				([k, v]) =>
					`<tr><td>${esc(layerName(k))}</td><td>${v.n}${
						v.bad
							? ` <span class="es-badge" data-theme="red">${__("{0} break", [
									v.bad,
							  ])}</span>`
							: ""
					}</td></tr>`
			)
			.join("");
	};
	const none = `<tr><td>${__("None")}</td></tr>`;
	return `<h2>${esc(layerName(id))}</h2>
		<div class="muted">${__("{0} folders, {1} files, {2} lines. {3} concepts.", [
			boxes.length,
			boxes.reduce((n, b) => n + b.files.length, 0),
			boxes.reduce((n, b) => n + b.lines, 0).toLocaleString(),
			l.concepts.length,
		])}</div>
		${l.note ? `<p>${esc(l.note)}</p>` : ""}
		<h3>${__("May use")}</h3><div>${
		l.mayUse.length
			? l.mayUse.map((m) => `<span class="es-badge">${esc(layerName(m))}</span>`).join("")
			: __("Nothing.")
	}</div>
		<h3>${__("Paths in {0}", ["layers.json"])}</h3><div>${
		l.paths.map((p) => `<code>${esc(p)}</code>`).join(" ") ||
		__("None: not in the import graph.")
	}</div>
		<h3>${__("Uses (imports to other layers)")}</h3><table>${byLayer(out, "to") || none}</table>
		<h3>${__("Used by")}</h3><table>${byLayer(inn, "from") || none}</table>
		<h3>${__("Concepts (the closed list)")}</h3>
		<table>${l.concepts
			.map((c) => `<tr><td>${md(c.name)}</td><td class="muted">${md(c.what)}</td></tr>`)
			.join("")}</table>
		<h3>${__("Ruling")}</h3><div>${__(
		"{0}. The target architecture ticket set the layers and the lists.",
		[archLink(l)]
	)}</div>`;
}
function boxDetail(id) {
	const b = box(id);
	const out = DATA.edges.filter((e) => e.from === id);
	const inn = DATA.edges.filter((e) => e.to === id);
	const loops = DATA.loops.filter((c) => c.includes(b.folder));
	const list = (edges, end) =>
		edges
			.sort((x, y) => y.count - x.count)
			.map(
				(e) =>
					`<tr><td><a href="#" data-select="edge" data-id="${esc(e.id)}">${esc(
						short(box(e[end]).folder)
					)}</a></td><td>${e.count}</td><td>${statusPill(e.status)}</td></tr>`
			)
			.join("");
	const ext = Object.entries(b.externals || {})
		.map(([k, v]) => `<span class="es-badge">${esc(k)} ${v}</span>`)
		.join("");
	const none = `<tr><td>${__("Nothing in the graph")}</td></tr>`;
	return `<h2><code>${esc(b.folder)}</code></h2>
		<div class="muted">${__("{0}. {1} files, {2} lines.", [
			esc(layerName(b.layer)),
			b.files.length,
			b.lines.toLocaleString(),
		])}</div>
		${
			loops.length
				? `<h3>${__("In a loop")}</h3>${loops
						.map(
							(c) =>
								`<p>${__("These {0} folders import each other: {1}", [
									c.length,
									c.map((f) => `<code>${esc(short(f))}</code>`).join(", "),
								])}</p>`
						)
						.join("")}`
				: ""
		}
		<h3>${__("Uses")}</h3><table>${list(out, "to") || none}</table>
		<h3>${__("Used by")}</h3><table>${list(inn, "from") || none}</table>
		${ext ? `<h3>${__("npm packages")}</h3><div>${ext}</div>` : ""}
		<h3>${__("Files")}</h3><table>${b.files
		.sort((x, y) => y.lines - x.lines)
		.map((f) => `<tr><td>${fileLink(f.path)}</td><td>${f.lines}</td></tr>`)
		.join("")}</table>
		<h3>${__("Concepts")}</h3><div>${__(
		"{0}. The concept tables name concepts per layer, not per folder.",
		[archLink(layer(b.layer))]
	)}</div>`;
}
function edgeDetail(id) {
	const e = DATA.edges.find((x) => x.id === id);
	const from = box(e.from),
		to = box(e.to);
	const owners = [...new Set(e.pairs.filter((p) => p.known !== null).map((p) => p.known))].map(
		(i) => DATA.knownBreaks[i]
	);
	return `<h2>${__("{0} uses {1}", [
		`<code>${esc(short(from.folder))}</code>`,
		`<code>${esc(short(to.folder))}</code>`,
	])}</h2>
		<div>${statusPill(e.status)} <span class="es-badge">${esc(e.kind)}</span> ${__("{0} file pairs", [
		e.count,
	])}</div>
		<p class="muted">${__("{0} to {1}.", [esc(layerName(from.layer)), esc(layerName(to.layer))])} ${
		e.status === "allowed"
			? __("The layer file allows this.")
			: e.status === "inside"
			? __("Both folders are in the same layer.")
			: e.status === "callback"
			? __(
					"A lower layer calls back what a higher layer registered. The layer file does not count this as a use."
			  )
			: __("{0} may use only: {1}.", [
					esc(layerName(from.layer)),
					layer(from.layer).mayUse.map(layerName).map(esc).join(", ") || __("nothing"),
			  ])
	}</p>
		${owners
			.map(
				(k) =>
					`<h3>${__("Known break")}</h3><p>${md(k.why)}</p><p>${__(
						"Removed by {0}: {1}",
						[
							`<a href="https://github.com/frappe/frappe/issues/${k.ticket}" target="_blank">#${k.ticket}</a>`,
							esc(k.title),
						]
					)}</p>`
			)
			.join("")}
		${
			e.status === "break"
				? `<h3>${__("What to do")}</h3><p>${__(
						'CI fails on this. Change the import so the lower layer does not use the higher one. If the rule is wrong, change {0} in the same PR and get a ruling: a new "may use" edge needs one.',
						["<code>layers.json</code>"]
				  )}</p>`
				: ""
		}
		<h3>${__("File pairs")}</h3><table>${e.pairs
		.map(
			(p) =>
				`<tr><td>${fileLink(p.from, p.line)}<br><span class="muted">${__(
					"to"
				)}</span> ${fileLink(p.to)}</td></tr>`
		)
		.join("")}</table>`;
}
function cellDetail(key) {
	const [f, t] = key.split(">");
	const edges = DATA.edges.filter((e) => box(e.from).layer === f && box(e.to).layer === t);
	const may = layer(f).mayUse.includes(t);
	return `<h2>${__("{0} uses {1}", [esc(layerName(f)), esc(layerName(t))])}</h2>
		<p>${
			f === t
				? __("Same layer.")
				: may
				? __("The layer file allows this.")
				: `<b style="color:${INK.red}">${__("The layer file does not allow this.")}</b>`
		}</p>
		<table>${edges
			.sort((x, y) => y.count - x.count)
			.map(
				(e) =>
					`<tr><td><a href="#" data-select="edge" data-id="${esc(e.id)}">${__(
						"{0} to {1}",
						[esc(short(box(e.from).folder)), esc(short(box(e.to).folder))]
					)}</a></td><td>${e.count}</td><td>${statusPill(e.status)}</td></tr>`
			)
			.join("")}</table>`;
}
function extDetail(i) {
	const x = DATA.extensions[i];
	return `<h2>${esc(x.name)}</h2>
		<div><span class="es-badge">${esc(x.tier)}</span> <span class="es-badge">${esc(
		layerName(x.layer)
	)}</span></div>
		<h3>${__("What it changes")}</h3><p>${esc(x.changes)}</p>
		<h3>${__("How it is registered")}</h3><p>${esc(x.how)}</p>
		${
			x.pair
				? `<h3>${__("Does the same job as")}</h3><p><b>${esc(x.pair)}</b>. ${esc(
						x.pairNote || ""
				  )}</p>`
				: ""
		}
		<h3>${__("Source")}</h3><p>${__("The ways to change the desk in {0}. The concept is in {1}.", [
		"ARCHITECTURE.md",
		archLink(layer(x.layer)),
	])}</p>`;
}
