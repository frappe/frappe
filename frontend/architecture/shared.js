// Constants and helpers shared by every part of the architecture page.
/* global DATA, drawLayers, drawMatrix, drawFlow, drawExtensions */
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
