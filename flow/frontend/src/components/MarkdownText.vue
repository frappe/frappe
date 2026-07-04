<script setup>
import { ref, watch, onUnmounted } from "vue";

// Renders streamed assistant text as markdown. Parsing the full accumulated
// string is O(n), so per-token would be O(n²); throttle to one parse per
// THROTTLE_MS with a guaranteed trailing parse. The model's output is
// untrusted, so the produced HTML is sanitized before injection.
// Takes the whole part (not part.text) so only this component reacts per token.
const props = defineProps({ part: { type: Object, required: true } });

const THROTTLE_MS = 100;
const html = ref("");
let timer = 0;
let last = 0;

// Tags markdown itself produces; anything else is dropped or unwrapped to text.
const ALLOWED = new Set(
	"P,BR,HR,H1,H2,H3,H4,H5,H6,UL,OL,LI,BLOCKQUOTE,PRE,CODE,EM,STRONG,DEL,TABLE,THEAD,TBODY,TR,TH,TD,A,IMG".split(
		","
	)
);
const DROPPED = new Set([
	"SCRIPT",
	"STYLE",
	"IFRAME",
	"OBJECT",
	"EMBED",
	"FORM",
	"LINK",
	"META",
	"BASE",
]);
// Leading "/" allows same-origin paths but not "//host" (protocol-relative → external).
const SAFE_URL = /^(https?:|mailto:|#|\/(?!\/))/i;

function sanitize(node) {
	for (const el of [...node.children]) {
		const tag = el.tagName.toUpperCase();
		if (DROPPED.has(tag)) {
			el.remove();
			continue;
		}
		sanitize(el);
		if (!ALLOWED.has(tag)) {
			el.replaceWith(...el.childNodes);
			continue;
		}
		for (const attr of [...el.attributes]) {
			const name = attr.name.toLowerCase();
			const keep =
				name === "title" ||
				name === "alt" ||
				(tag === "A" && name === "href" && SAFE_URL.test(attr.value)) ||
				(tag === "IMG" && name === "src" && SAFE_URL.test(attr.value));
			if (!keep) el.removeAttribute(attr.name);
		}
		// The panel overlays the desk; links must not navigate the page away.
		if (tag === "A") {
			el.setAttribute("target", "_blank");
			el.setAttribute("rel", "noopener noreferrer");
		}
	}
}

function render() {
	timer = 0;
	last = performance.now();
	let raw = props.part.text || "";
	// Close an unterminated fence so streamed code renders as a block, not raw text.
	if ((raw.match(/```/g) || []).length % 2 === 1) raw += "\n```";

	if (!window.frappe?.markdown) {
		html.value = escapeHtml(raw);
		return;
	}
	const doc = new DOMParser().parseFromString(frappe.markdown(raw), "text/html");
	sanitize(doc.body);
	// Let a wide table scroll in its own box instead of widening the panel.
	for (const table of [...doc.body.querySelectorAll("table")]) {
		const wrap = doc.createElement("div");
		wrap.className = "md-table-scroll";
		table.replaceWith(wrap);
		wrap.appendChild(table);
	}
	html.value = doc.body.innerHTML;
}

function schedule() {
	// A pending timer will read the freshest text when it fires, so coalesce.
	if (timer) return;
	const elapsed = performance.now() - last;
	if (elapsed >= THROTTLE_MS) render();
	else timer = setTimeout(render, THROTTLE_MS - elapsed);
}

function escapeHtml(s) {
	return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

watch(() => props.part.text, schedule, { immediate: true });
onUnmounted(() => timer && clearTimeout(timer));
</script>

<template>
	<div class="md" v-html="html"></div>
</template>
