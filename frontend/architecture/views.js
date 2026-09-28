// The four views of the architecture page and the switcher between them.
/* global DATA, VIEWS, ORDER, COLOR, GH, state, inLoop, layer, box, isBreak, esc, md, short, layerName, stats, idleDetail */
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
		svg += `<g class="layerlabel" onclick="select('layer','${id}')"><rect x="0" y="${y}" width="${
			LABEL - 8
		}" height="${ROW}" rx="6" fill="#fff" stroke="#dde1e6"/>
			<rect x="0" y="${y}" width="5" height="${ROW}" rx="2" fill="${COLOR[id]}"/>
			<text x="12" y="${y + 20}" style="font-weight:600;font-size:12px">${esc(layerName(id))}</text>
			<text x="12" y="${y + 38}" fill="#57606a">${
			bs.length
				? `${bs.length} ${
						bs.length === 1 ? "folder" : "folders"
				  }, ${lines.toLocaleString()} lines, ${l.concepts.length} concepts`
				: `${l.concepts.length} concepts, not in the graph`
		}</text></g>`;
		if (!bs.length)
			svg += `<rect x="${LABEL}" y="${y}" width="${avail}" height="${ROW}" rx="4" fill="none" stroke="#c9ced4" stroke-dasharray="4 3"/>
			<text x="${LABEL + 10}" y="${
				y + 31
			}" fill="#8c959f">App folders and Client Script rows. They reach the desk only through the import list and the page object.</text>`;
	});
	svg += `<text x="${bx}" y="${
		bTop - 8
	}" style="font-weight:600;font-size:12px" class="layerlabel">The build (beside)</text>`;

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
			const stroke = isBreak(e)
				? "#c62828"
				: e.status === "callback"
				? "#0b5cad"
				: sel
				? e.from === sel
					? "#3b4a5a"
					: "#1a7f37"
				: "#8c959f";
			const width = isBreak(e) ? 2.2 : Math.min(4, 0.8 + Math.log2(e.count + 1) * 0.5);
			const dash = e.status === "known" ? `stroke-dasharray="6 3"` : "";
			const op = isBreak(e) || sel ? 0.9 : 0.25;
			return `<path class="edge" d="${d}" stroke="${stroke}" stroke-width="${width}" ${dash} opacity="${op}"/>
			<path class="edge hit" d="${d}" onclick="select('edge','${e.id}')"><title>${esc(
				short(box(e.from).folder)
			)} to ${esc(short(box(e.to).folder))}: ${e.count} (${e.status})</title></path>`;
		})
		.join("");

	for (const b of DATA.boxes) {
		const p = pos.get(b.id);
		if (!p) continue;
		const cls = [
			"box",
			sel === b.id ? "sel" : "",
			linked && !linked.has(b.id) ? "dim" : "",
			state.showLoops && inLoop.has(b.folder) ? "loop" : "",
		].join(" ");
		const name =
			b.files.length === 1
				? b.files[0].path.split("/").pop()
				: short(b.folder).split("/").pop();
		const fits = p.w > 52;
		svg += `<g class="${cls}" onclick="select('box','${b.id}')"><title>${esc(b.folder)}: ${
			b.files.length
		} files, ${b.lines} lines</title>
			<rect x="${p.x}" y="${p.y}" width="${p.w}" height="${p.h}" rx="4" fill="${
			COLOR[b.layer]
		}" opacity="${0.55 + Math.min(0.45, b.lines / 6000)}"/>
			${
				fits
					? `<text x="${p.x + 5}" y="${
							p.y + 20
					  }" fill="#fff" style="font-weight:600">${esc(
							name.length * 6.2 > p.w - 8
								? name.slice(0, Math.floor((p.w - 8) / 6.2)) + "…"
								: name
					  )}</text>
			<text x="${p.x + 5}" y="${p.y + 37}" fill="#fff" opacity=".85">${b.lines.toLocaleString()}</text>`
					: ""
			}</g>`;
	}
	svg += edgeSvg + `</svg>`;

	view.innerHTML =
		`<div class="legend">
		<span><i style="border-color:#c62828"></i>new break (CI fails)</span>
		<span><i style="border-color:#c62828;border-top-style:dashed"></i>known break (has a ticket)</span>
		<span><i style="border-color:#0b5cad"></i>callback</span>
		<label><input type="checkbox" ${
			state.showAll ? "checked" : ""
		} onchange="state.showAll=this.checked;drawLayers()"> show all ${
			DATA.edges.length
		} edges</label>
		<label><input type="checkbox" ${
			state.showLoops ? "checked" : ""
		} onchange="state.showLoops=this.checked;drawLayers()"> mark folders in loops</label>
		${
			sel
				? `<a href="#" onclick="state.selected=null;document.getElementById('panel').innerHTML=idleDetail();drawLayers();return false">clear selection</a>`
				: ""
		}
		<span>Box width: share of its layer's lines.</span></div>` + svg;
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
	let html = `<p class="muted">Rows use columns. A green cell is a use the layer file allows; a grey cell is one it does not. A number is the count of file pairs; red means the code does what the layer file forbids. Customization is left out: it is not in the import graph.</p>
		<table class="matrix"><tr><th class="row">uses →</th>${ids
			.map(
				(c) =>
					`<th title="${esc(layerName(c))}">${
						c === "main" ? "main" : c === "build" ? "build" : c
					}</th>`
			)
			.join("")}</tr>`;
	for (const r of ids) {
		html += `<tr><th class="row"><a href="#" onclick="select('layer','${r}');return false">${esc(
			layerName(r)
		)}</a></th>`;
		for (const c of ids) {
			const s = sum[r + ">" + c];
			const may = layer(r).mayUse.includes(c);
			const cls = r === c ? "self" : s?.bad ? "bad" : may ? "may" : "no";
			html += `<td class="${cls} ${s ? "has" : ""}" ${
				s ? `onclick="select('cell','${r}>${c}')"` : ""
			}>${s ? s.n : ""}</td>`;
		}
		html += `</tr>`;
	}
	html += `</table>
		<h3 style="margin-top:22px">Folder loops</h3>
		<p class="muted">Groups of folders that import each other. The layer file cannot show these; the loop check does.</p>
		<table class="matrix">${DATA.loops
			.map(
				(c) =>
					`<tr><td style="text-align:left">${
						c.length
					} folders</td><td style="text-align:left">${c
						.map((f) => `<code>${esc(short(f))}</code>`)
						.join(" ")}</td></tr>`
			)
			.join("")}</table>`;
	document.getElementById("view").innerHTML = html;
}

function drawFlow() {
	const flow = DATA.flows[state.flow];
	const step = flow.steps[state.step];
	const lit = new Set(step.layers);
	const server = lit.has("1") || lit.has("2");
	const stack = ["index.html", ...ORDER]
		.map((id) => {
			const on = lit.has(id);
			const name = id === "index.html" ? "index.html (inline script)" : layerName(id);
			return `<div class="${on ? "lit" : ""}" style="${
				on ? `background:${COLOR[id] || "#57606a"}` : ""
			}">${esc(name)}</div>`;
		})
		.join("");
	document.getElementById("view").innerHTML = `
		<div class="flowtabs">${DATA.flows
			.map(
				(f, i) =>
					`<button class="${
						i === state.flow ? "on" : ""
					}" onclick="state.flow=${i};state.step=0;drawFlow()">${md(
						f.title.split(":")[0]
					)}</button>`
			)
			.join("")}</div>
		<h2 style="font-size:15px;margin:0 0 4px">${md(flow.title)}</h2>
		<p class="muted">Budget: ${md(flow.budget)} Up and down arrows move between steps.</p>
		<div class="flow"><div>${flow.steps
			.map(
				(s, i) => `<div class="step ${
					i === state.step ? "on" : ""
				}" onclick="state.step=${i};drawFlow()">
			<span class="n">${esc(s.n)}</span>${md(s.step)}
			${
				i === state.step
					? `<div style="margin-top:6px">
				<div><span class="pill">layers ${esc(s.layerText)}</span>${
							server ? `<span class="pill server">goes to the server</span>` : ""
					  }</div>
				<div style="margin-top:4px"><b>Permission check:</b> ${md(s.check)}</div>
				<div><b>Cache and key:</b> ${md(s.cache)}</div></div>`
					: ""
			}</div>`
			)
			.join("")}</div>
		<div class="stack">${stack}</div></div>`;
	document.getElementById("panel").innerHTML = `<h2>Step ${esc(step.n)}</h2><p>${md(
		step.step
	)}</p>
		<h3>Layers</h3><div>${[...lit]
			.map(
				(l) =>
					`<span class="pill" style="background:${
						COLOR[l] || "#57606a"
					};color:#fff">${esc(l === "index.html" ? l : layerName(l))}</span>`
			)
			.join("")}</div>
		<h3>Permission check</h3><p>${md(step.check)}</p><h3>Cache and key</h3><p>${md(step.cache)}</p>
		<h3>Not shown</h3><p class="muted">The files each step passes through, and its request. <code>ARCHITECTURE.md</code> names layers per step, not files or requests.</p>
		<h3>Source</h3><p><a href="${GH}${
		DATA.architecture
	}#the-five-flows" target="_blank">ARCHITECTURE.md, the five flows</a></p>`;
}

function drawExtensions() {
	const tiers = [
		["app", "An app"],
		["site", "A site admin"],
		["user", "A user"],
	];
	const pairs = DATA.extensions.filter((x) => x.pair).length;
	document.getElementById("view").innerHTML = `<p class="muted">${
		DATA.extensions.length
	} ways to change the desk, by who uses them. ${pairs} rows name another row that does the same job. Hover a card to see its pair. The list is kept by hand in <code>frontend/architecture/extensions.json</code>.</p>
		<div class="ext">${tiers
			.map(
				([t, title]) =>
					`<div><h2>${title}</h2>${DATA.extensions
						.map((x, i) =>
							x.tier !== t
								? ""
								: `<div class="card" data-name="${esc(x.name)}" data-pair="${esc(
										x.pair || ""
								  )}" style="border-left-color:${
										COLOR[x.layer]
								  }" onclick="select('ext',${i})" onmouseenter="pairHit(this,true)" onmouseleave="pairHit(this,false)">
				<b>${esc(x.name)}</b><div class="muted">${esc(x.changes)}</div>
				<div><span class="pill">${esc(layerName(x.layer))}</span>${
										x.pair
											? `<span class="pair">same job as ${esc(
													x.pair
											  )}</span>`
											: ""
								  }</div></div>`
						)
						.join("")}</div>`
			)
			.join("")}</div>`;
}
function pairHit(el, on) {
	for (const c of document.querySelectorAll(".card")) {
		if (c.dataset.name === el.dataset.pair || c.dataset.pair === el.dataset.name)
			c.classList.toggle("pairhit", on);
	}
}

function current() {
	const key = new URLSearchParams(location.search).get("view") || "A";
	return VIEWS.find((v) => v.key === key) || VIEWS[0];
}
function go(step) {
	const i = (VIEWS.indexOf(current()) + step + VIEWS.length) % VIEWS.length;
	const url = new URL(location.href);
	url.searchParams.set("view", VIEWS[i].key);
	history.replaceState(null, "", url);
	render();
}
function render() {
	const v = current();
	document.getElementById("label").textContent = `${v.key}: ${v.name}`;
	state.selected = null;
	document.getElementById("panel").innerHTML = idleDetail();
	v.draw();
}
document.getElementById("prev").onclick = () => go(-1);
document.getElementById("next").onclick = () => go(1);
addEventListener("keydown", (e) => {
	if (e.target.closest("input, textarea, [contenteditable]")) return;
	if (e.key === "ArrowLeft") go(-1);
	if (e.key === "ArrowRight") go(1);
	if (current().key === "C" && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
		const n = DATA.flows[state.flow].steps.length;
		state.step = (state.step + (e.key === "ArrowDown" ? 1 : -1) + n) % n;
		e.preventDefault();
		drawFlow();
	}
});
addEventListener("resize", () => current().key === "A" && drawLayers());
stats();
render();
