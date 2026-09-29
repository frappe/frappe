// Views C and D, the switcher between the four views, and the page's listeners.
/* global DATA, VIEWS, ORDER, GH, state, esc, md, layerName, layerClass, idleDetail, select, drawLayers, stats */
function drawFlow() {
	const flow = DATA.flows[state.flow];
	const step = flow.steps[state.step];
	const lit = new Set(step.layers);
	const server = lit.has("1") || lit.has("2");
	const stack = ["index.html", ...ORDER]
		.map((id) => {
			const on = lit.has(id);
			const name =
				id === "index.html" ? __("{0} (inline script)", ["index.html"]) : layerName(id);
			return `<div class="${on ? `lit ${layerClass(id)}` : ""}">${esc(name)}</div>`;
		})
		.join("");
	document.getElementById("view").innerHTML = `
		<div class="flowtabs">${DATA.flows
			.map(
				(f, i) =>
					`<button class="es-button"${
						i === state.flow ? ' data-variant="solid"' : ""
					} onclick="state.flow=${i};state.step=0;drawFlow()">${md(
						f.title.split(":")[0]
					)}</button>`
			)
			.join("")}</div>
		<h2 class="title">${md(flow.title)}</h2>
		<p class="muted">${__("Budget: {0} Up and down arrows move between steps.", [md(flow.budget)])}</p>
		<div class="flow"><div>${flow.steps
			.map(
				(s, i) => `<div class="step ${
					i === state.step ? "on" : ""
				}" onclick="state.step=${i};drawFlow()">
			<span class="n">${esc(s.n)}</span>${md(s.step)}
			${
				i === state.step
					? `<div class="more">
				<div><span class="es-badge">${__("layers {0}", [esc(s.layerText)])}</span>${
							server
								? `<span class="es-badge" data-theme="amber">${__(
										"goes to the server"
								  )}</span>`
								: ""
					  }</div>
				<div class="check"><b>${__("Permission check:")}</b> ${md(s.check)}</div>
				<div><b>${__("Cache and key:")}</b> ${md(s.cache)}</div></div>`
					: ""
			}</div>`
			)
			.join("")}</div>
		<div class="stack">${stack}</div></div>`;
	document.getElementById("panel").innerHTML = `<h2>${__("Step {0}", [esc(step.n)])}</h2><p>${md(
		step.step
	)}</p>
		<h3>${__("Layers")}</h3><div>${[...lit]
		.map(
			(l) =>
				`<span class="es-badge chip ${layerClass(l)}">${esc(
					l === "index.html" ? l : layerName(l)
				)}</span>`
		)
		.join("")}</div>
		<h3>${__("Permission check")}</h3><p>${md(step.check)}</p>
		<h3>${__("Cache and key")}</h3><p>${md(step.cache)}</p>
		<h3>${__("Not shown")}</h3><p class="muted">${__(
		"The files each step passes through, and its request. {0} names layers per step, not files or requests.",
		["<code>ARCHITECTURE.md</code>"]
	)}</p>
		<h3>${__("Source")}</h3><p><a href="${GH}${DATA.architecture}#the-five-flows" target="_blank">${__(
		"{0}, the five flows",
		["ARCHITECTURE.md"]
	)}</a></p>`;
}

function drawExtensions() {
	const tiers = [
		["app", __("An app")],
		["site", __("A site admin")],
		["user", __("A user")],
	];
	const pairs = DATA.extensions.filter((x) => x.pair).length;
	document.getElementById("view").innerHTML = `<p class="muted">${__(
		"{0} ways to change the desk, by who uses them. {1} rows name another row that does the same job. Hover a card to see its pair. The list comes from {2}.",
		[DATA.extensions.length, pairs, "ARCHITECTURE.md"]
	)}</p>
		<div class="ext">${tiers
			.map(
				([t, title]) =>
					`<div><h2>${title}</h2>${DATA.extensions
						.map((x, i) =>
							x.tier !== t
								? ""
								: `<div class="card ${layerClass(x.layer)}" data-name="${esc(
										x.name
								  )}" data-pair="${esc(
										x.pair || ""
								  )}" data-select="ext" data-id="${i}" onmouseenter="pairHit(this,true)" onmouseleave="pairHit(this,false)">
				<b>${esc(x.name)}</b><div class="muted">${esc(x.changes)}</div>
				<div><span class="es-badge">${esc(layerName(x.layer))}</span>${
										x.pair
											? `<span class="pair">${__("same job as {0}", [
													esc(x.pair),
											  ])}</span>`
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
// One listener for every clickable item, so no repo text lands inside an inline handler.
document.addEventListener("click", (event) => {
	const item = event.target.closest("[data-select]");
	if (!item) return;
	event.preventDefault();
	select(item.dataset.select, item.dataset.id);
});
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
document.title = document.getElementById("title").textContent = __("Desk v2 architecture");
document.getElementById("prev").title = __("Previous view (Left arrow)");
document.getElementById("next").title = __("Next view (Right arrow)");
stats();
render();
