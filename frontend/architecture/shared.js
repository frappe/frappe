// Constants and helpers shared by every part of the architecture page.
/* global MESSAGES, DATA, drawLayers, drawMatrix, drawFlow, drawExtensions */
const VIEWS = [
	{ key: "A", name: __("Layers"), draw: drawLayers },
	{ key: "B", name: __("Layer matrix"), draw: drawMatrix },
	{ key: "C", name: __("Flows, step by step"), draw: drawFlow },
	{ key: "D", name: __("Ways to change the desk"), draw: drawExtensions },
];
const ORDER = ["main", "9", "8", "7", "6", "5", "4", "3", "2", "1", "build"];
// Espresso palette steps: gray-700, gray-600, purple-700, purple-500, violet-600, blue-600,
// teal-600, green-700, amber-700, yellow-800, orange-600 (hex from espresso/colors.css).
// Espresso tokens, with fallbacks for a copy opened from disk.
const COLOR = {
	main: "var(--gray-700, #525252)",
	9: "var(--gray-600, #7c7c7c)",
	8: "var(--purple-700, #6e399d)",
	7: "var(--purple-500, #9c45e3)",
	6: "var(--violet-600, #6e57d1)",
	5: "var(--blue-600, #077ddf)",
	4: "var(--teal-600, #0a857b)",
	3: "var(--green-700, #14804d)",
	2: "var(--amber-700, #bb6f0c)",
	1: "var(--yellow-800, #8c5600)",
	build: "var(--orange-600, #d35a09)",
};
const INK = {
	red: "var(--ink-red-7, #c62828)",
	blue: "var(--ink-blue-7, #0b5cad)",
	green: "var(--ink-green-8, #1a7f37)",
	line: "var(--ink-gray-4, #8c959f)",
	strong: "var(--ink-gray-7, #3b4a5a)",
	muted: "var(--ink-gray-5, #57606a)",
	on: "var(--white, #fff)",
	surface: "var(--surface-base, #fff)",
	outline: "var(--outline-gray-2, #dde1e6)",
	dashed: "var(--outline-gray-3, #c9ced4)",
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
	const theme = { break: "red", known: "red", allowed: "green", callback: "blue" }[s];
	return `<span class="es-badge"${theme ? ` data-theme="${theme}"` : ""}>${text}</span>`;
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
