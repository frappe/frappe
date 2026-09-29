// Constants and helpers shared by every part of the architecture page.
/* global MESSAGES, DATA, drawLayers, drawMatrix, drawFlow, drawExtensions */
const VIEWS = [
	{ key: "A", name: __("Layers"), draw: drawLayers },
	{ key: "B", name: __("Layer matrix"), draw: drawMatrix },
	{ key: "C", name: __("Flows, step by step"), draw: drawFlow },
	{ key: "D", name: __("Ways to change the desk"), draw: drawExtensions },
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

// The desk's shape: `{0}` fills by position. The route passes MESSAGES for the user's language.
function __(text, replacements) {
	const translated = MESSAGES[text] || text;
	return replacements
		? translated.replace(/\{(\d+)\}/g, (m, i) => replacements[Number(i)] ?? m)
		: translated;
}
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
		.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (m, t, u) => {
			const href = linkTarget(u);
			return href ? `<a href="${href}" target="_blank">${t}</a>` : t;
		});
}
// Links in ARCHITECTURE.md are relative to it; anything but these is shown as text.
function linkTarget(u) {
	if (u.startsWith("#")) return GH + DATA.architecture + u;
	if (u.startsWith("./")) return GH + "frontend/" + u.slice(2);
	if (u.startsWith("https://")) return u;
	return null;
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
		break: __("new break"),
		known: __("known break"),
		allowed: __("allowed"),
		inside: __("same layer"),
		callback: __("callback, not a use"),
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
	const bold = (n) => `<b>${n}</b>`;
	document.getElementById("stats").innerHTML = [
		__("Built from {0} at {1}, {2}", [bold(DATA.branch), bold(DATA.commit), DATA.builtAt]),
		`<span>${__("{0} files, {1} lines", [bold(files), bold(lines.toLocaleString())])}</span>`,
		`<span class="red">${__("{0} new breaks", [bold(fresh)])}</span>`,
		`<span class="red">${__("{0} known breaks", [bold(breaks.length - fresh)])}</span>`,
		`<span>${__("{0} folder loops", [bold(DATA.loops.length)])}</span>`,
		DATA.unplaced.length
			? `<span class="red">${__("{0} files in no layer", [
					bold(DATA.unplaced.length),
			  ])}</span>`
			: "",
	].join("");
}
