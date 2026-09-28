// Shared helpers and the details panel of the architecture page.
/* global DATA, current, drawLayers, drawMatrix, drawFlow, drawExtensions */
const VIEWS = [
	{ key: "A", name: "Layers", draw: drawLayers },
	{ key: "B", name: "Layer matrix", draw: drawMatrix },
	{ key: "C", name: "Flows, step by step", draw: drawFlow },
	{ key: "D", name: "Ways to change the desk", draw: drawExtensions },
];
const ORDER = ["main", "9", "8", "7", "6", "5", "4", "3", "2", "1", "build"];
const COLOR = {
	main: "#57606a",
	9: "#8c959f",
	8: "#6f42c1",
	7: "#8250df",
	6: "#5a67d8",
	5: "#3b82c4",
	4: "#1b998b",
	3: "#16806f",
	2: "#b7791f",
	1: "#8a6116",
	build: "#c05621",
};
const GH = "https://github.com/frappe/frappe/blob/desk-v2/";
const layer = (id) => DATA.layers.find((l) => l.id === id);
const box = (id) => DATA.boxes.find((b) => b.id === id);
const isBreak = (e) => e.status === "break" || e.status === "known";
const inLoop = new Set(DATA.loops.flat());
const state = { selected: null, showAll: false, showLoops: false, flow: 2, step: 0 };

function esc(s) {
	return String(s).replace(
		/[&<>"]/g,
		(c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])
	);
}
function md(s) {
	return esc(s)
		.replace(/`([^`]+)`/g, "<code>$1</code>")
		.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
		.replace(
			/\[([^\]]+)\]\(([^)]+)\)/g,
			(m, t, u) =>
				`<a href="${
					u.startsWith("#") ? GH + DATA.architecture + u : u
				}" target="_blank">${t}</a>`
		);
}
function short(folder) {
	return folder
		.replace(/^frontend\/src\//, "")
		.replace(/^ui\/src\//, "ui/")
		.replace(/^frappe\//, "frappe/");
}
function fileLink(p, line) {
	return `<a href="${GH}${p}${line ? "#L" + line : ""}" target="_blank"><code>${esc(p)}${
		line ? ":" + line : ""
	}</code></a>`;
}
function statusPill(s) {
	const text = {
		break: "new break",
		known: "known break",
		allowed: "allowed",
		inside: "same layer",
		callback: "callback, not a use",
	}[s];
	return `<span class="pill ${s}">${text}</span>`;
}
function layerName(id) {
	const l = layer(id);
	return `${/^\d$/.test(id) ? id + ". " : ""}${l.name}`;
}
function archLink(l) {
	return `<a href="${GH}${DATA.architecture}#${
		l.section
	}" target="_blank">ARCHITECTURE.md, ${esc(layerName(l.id))}</a>`;
}
function stats() {
	const breaks = DATA.edges.filter(isBreak).flatMap((e) => e.pairs);
	const fresh = breaks.filter((p) => p.known === null).length;
	const files = DATA.boxes.reduce((n, b) => n + b.files.length, 0);
	const lines = DATA.boxes.reduce((n, b) => n + b.lines, 0);
	document.getElementById("stats").innerHTML = [
		`Built from <b>${DATA.branch}</b> at <b>${DATA.commit}</b>, ${DATA.builtAt}`,
		`<span><b>${files}</b> files, <b>${lines.toLocaleString()}</b> lines</span>`,
		`<span class="red"><b>${fresh}</b> new breaks</span>`,
		`<span class="red"><b>${breaks.length - fresh}</b> known breaks</span>`,
		`<span><b>${DATA.loops.length}</b> folder loops</span>`,
		DATA.unplaced.length
			? `<span class="red"><b>${DATA.unplaced.length}</b> files in no layer</span>`
			: "",
	].join("");
}

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
		)}</code> (the concepts and the flows). Only the "Ways to change the desk" view is kept by hand, in <code>frontend/architecture/extensions.json</code>.</p>`;
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
					`<tr><td><a href="#" onclick="select('edge','${e.id}');return false">${esc(
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
					`<tr><td><a href="#" onclick="select('edge','${e.id}');return false">${esc(
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
		<h3>Source</h3><p>Kept by hand in <code>frontend/architecture/extensions.json</code>. The concept is in ${archLink(
			layer(x.layer)
		)}.</p>`;
}
