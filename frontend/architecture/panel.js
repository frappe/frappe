// The details panel: what one click on a layer, a folder, a line or a card shows.
/* global DATA, VIEWS, ORDER, state, current, drawLayers, esc, md, short, layer, box, isBreak, layerName, archLink, statusPill, fileLink */
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
	return `<h2>Click anything</h2>
		<p class="muted">A layer name, a folder, a line between folders, a matrix cell, a flow step or a card. The details show here.</p>
		<h3>Read the colours</h3>
		<p>A <b style="color:#c62828">red</b> line or cell is an import that the layer file does not allow. Dashed red is a known break: the layer file lists it with the ticket that removes it. Solid red is new: CI fails on it.</p>
		<p>An orange dashed outline marks a folder inside a loop, where folders import each other.</p>
		<h3>Where the data comes from</h3>
		<p>Built on each request from the code (the import graph), <code>frontend/architecture/layers.json</code> (which layer may use which) and <code>${esc(
			DATA.architecture
		)}</code> (the concepts and the flows). The ways to change the desk come from the same file.</p>`;
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
						v.bad ? ` <span class="pill break">${v.bad} break</span>` : ""
					}</td></tr>`
			)
			.join("");
	};
	return `<h2>${esc(layerName(id))}</h2>
		<div class="muted">${boxes.length} folders, ${boxes.reduce(
		(n, b) => n + b.files.length,
		0
	)} files, ${boxes.reduce((n, b) => n + b.lines, 0).toLocaleString()} lines. ${
		l.concepts.length
	} concepts.</div>
		${l.note ? `<p>${esc(l.note)}</p>` : ""}
		<h3>May use</h3><div>${
			l.mayUse.length
				? l.mayUse.map((m) => `<span class="pill">${esc(layerName(m))}</span>`).join("")
				: "Nothing."
		}</div>
		<h3>Paths in layers.json</h3><div>${
			l.paths.map((p) => `<code>${esc(p)}</code>`).join(" ") ||
			"None: not in the import graph."
		}</div>
		<h3>Uses (imports to other layers)</h3><table>${
			byLayer(out, "to") || "<tr><td>None</td></tr>"
		}</table>
		<h3>Used by</h3><table>${byLayer(inn, "from") || "<tr><td>None</td></tr>"}</table>
		<h3>Concepts (the closed list)</h3>
		<table>${l.concepts
			.map((c) => `<tr><td>${md(c.name)}</td><td class="muted">${md(c.what)}</td></tr>`)
			.join("")}</table>
		<h3>Ruling</h3><div>${archLink(
			l
		)}. The target architecture ticket set the layers and the lists.</div>`;
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
		.map(([k, v]) => `<span class="pill">${esc(k)} ${v}</span>`)
		.join("");
	return `<h2><code>${esc(b.folder)}</code></h2>
		<div class="muted">${esc(layerName(b.layer))}. ${
		b.files.length
	} files, ${b.lines.toLocaleString()} lines.</div>
		${
			loops.length
				? `<h3>In a loop</h3>${loops
						.map(
							(c) =>
								`<p>These ${c.length} folders import each other: ${c
									.map((f) => `<code>${esc(short(f))}</code>`)
									.join(", ")}</p>`
						)
						.join("")}`
				: ""
		}
		<h3>Uses</h3><table>${list(out, "to") || "<tr><td>Nothing in the graph</td></tr>"}</table>
		<h3>Used by</h3><table>${list(inn, "from") || "<tr><td>Nothing in the graph</td></tr>"}</table>
		${ext ? `<h3>npm packages</h3><div>${ext}</div>` : ""}
		<h3>Files</h3><table>${b.files
			.sort((x, y) => y.lines - x.lines)
			.map((f) => `<tr><td>${fileLink(f.path)}</td><td>${f.lines}</td></tr>`)
			.join("")}</table>
		<h3>Concepts</h3><div>${archLink(
			layer(b.layer)
		)}. The concept tables name concepts per layer, not per folder.</div>`;
}
function edgeDetail(id) {
	const e = DATA.edges.find((x) => x.id === id);
	const from = box(e.from),
		to = box(e.to);
	const owners = [...new Set(e.pairs.filter((p) => p.known !== null).map((p) => p.known))].map(
		(i) => DATA.knownBreaks[i]
	);
	return `<h2><code>${esc(short(from.folder))}</code> uses <code>${esc(
		short(to.folder)
	)}</code></h2>
		<div>${statusPill(e.status)} <span class="pill">${esc(e.kind)}</span> ${e.count} file pairs</div>
		<p class="muted">${esc(layerName(from.layer))} to ${esc(layerName(to.layer))}. ${
		e.status === "allowed"
			? "The layer file allows this."
			: e.status === "inside"
			? "Both folders are in the same layer."
			: e.status === "callback"
			? "A lower layer calls back what a higher layer registered. The layer file does not count this as a use."
			: `${esc(layerName(from.layer))} may use only: ${
					layer(from.layer).mayUse.map(layerName).map(esc).join(", ") || "nothing"
			  }.`
	}</p>
		${owners
			.map(
				(k) =>
					`<h3>Known break</h3><p>${md(
						k.why
					)}</p><p>Removed by <a href="https://github.com/frappe/frappe/issues/${
						k.ticket
					}" target="_blank">#${k.ticket}</a>: ${esc(k.title)}</p>`
			)
			.join("")}
		${
			e.status === "break"
				? `<h3>What to do</h3><p>CI fails on this. Change the import so the lower layer does not use the higher one. If the rule is wrong, change <code>layers.json</code> in the same PR and get a ruling: a new "may use" edge needs one.</p>`
				: ""
		}
		<h3>File pairs</h3><table>${e.pairs
			.map(
				(p) =>
					`<tr><td>${fileLink(
						p.from,
						p.line
					)}<br><span class="muted">to</span> ${fileLink(p.to)}</td></tr>`
			)
			.join("")}</table>`;
}
function cellDetail(key) {
	const [f, t] = key.split(">");
	const edges = DATA.edges.filter((e) => box(e.from).layer === f && box(e.to).layer === t);
	const may = layer(f).mayUse.includes(t);
	return `<h2>${esc(layerName(f))} uses ${esc(layerName(t))}</h2>
		<p>${
			f === t
				? "Same layer."
				: may
				? "The layer file allows this."
				: "<b style='color:#c62828'>The layer file does not allow this.</b>"
		}</p>
		<table>${edges
			.sort((x, y) => y.count - x.count)
			.map(
				(e) =>
					`<tr><td><a href="#" data-select="edge" data-id="${esc(e.id)}">${esc(
						short(box(e.from).folder)
					)} to ${esc(short(box(e.to).folder))}</a></td><td>${
						e.count
					}</td><td>${statusPill(e.status)}</td></tr>`
			)
			.join("")}</table>`;
}
function extDetail(i) {
	const x = DATA.extensions[i];
	return `<h2>${esc(x.name)}</h2>
		<div><span class="pill">${esc(x.tier)}</span> <span class="pill">${esc(
		layerName(x.layer)
	)}</span></div>
		<h3>What it changes</h3><p>${esc(x.changes)}</p>
		<h3>How it is registered</h3><p>${esc(x.how)}</p>
		${
			x.pair
				? `<h3>Does the same job as</h3><p><b>${esc(x.pair)}</b>. ${esc(
						x.pairNote || ""
				  )}</p>`
				: ""
		}
		<h3>Source</h3><p>The ways to change the desk in ARCHITECTURE.md. The concept is in ${archLink(
			layer(x.layer)
		)}.</p>`;
}
