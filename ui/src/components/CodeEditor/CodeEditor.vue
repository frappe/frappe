<template>
	<div ref="el" class="code-editor" />
</template>

<script setup lang="ts">
// Writer primitive: a CodeMirror 6 editor, nothing else (no preview logic — that
// lives in the sibling `CodePreview`). CodeMirror is lazy-loaded in `onMounted`
// via dynamic `import()` (the `GeolocationField` convention) so the static graph
// stays editor-free and each language tree-shakes into its own async chunk —
// apps that never render a code field pay no runtime cost.
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { EditorView } from "@codemirror/view";
import type { Compartment, Extension } from "@codemirror/state";
import { loadLanguage } from "./languages";
import type { CodeEditorEmits, CodeEditorProps } from "./types";

const props = withDefaults(defineProps<CodeEditorProps>(), {
	language: "plain",
	readonly: false,
	placeholder: "",
	variant: "subtle",
});
const emit = defineEmits<CodeEditorEmits>();

const el = ref<HTMLElement | null>(null);

let view: EditorView | null = null;
let languageCompartment: Compartment | null = null;
let readonlyCompartment: Compartment | null = null;
let variantCompartment: Compartment | null = null;
// Imported CodeMirror modules, held so the watchers can reconfigure without a
// second dynamic import.
let cmView: typeof import("@codemirror/view") | null = null;
let cmState: typeof import("@codemirror/state") | null = null;
// Guards the `modelValue` watcher against the editor's own `updateListener`: when
// we dispatch an external change (e.g. the wrapper's JSON pretty-print) we must
// not echo it straight back out as fresh input.
let syncingFromProp = false;
// Tracks whether content overflows `maxHeight` so the `overflow` emit only fires
// on transitions, not on every keystroke. The observer watches the scroller box.
let overflowObserver: ResizeObserver | null = null;
let lastOverflow = false;
// `onMounted` is async (it awaits CodeMirror's dynamic imports). If the component
// unmounts mid-load, `onBeforeUnmount` runs while `view` is still null and its
// cleanup no-ops — then the resumed `onMounted` would create an orphan view +
// observer that nothing destroys. This flag lets the resume bail instead.
let destroyed = false;

// Push `maxHeight` onto the editor via a CSS var (the theme reads
// `var(--cm-max-height, none)`), then re-check overflow.
function applyMaxHeight() {
	if (el.value) el.value.style.setProperty("--cm-max-height", props.maxHeight ?? "none");
	measureOverflow();
}

// Emit when the scroller becomes (un)scrollable — i.e. content crosses the cap.
function measureOverflow() {
	if (!view) return;
	const s = view.scrollDOM;
	const overflowing = s.scrollHeight > s.clientHeight + 1;
	if (overflowing === lastOverflow) return;
	lastOverflow = overflowing;
	emit("overflow", overflowing);
}

// Build the language `Compartment` contents for a key. For `json` we also wire
// the lint gutter + parse linter so invalid JSON is marked inline at its
// position — the field contract has no error channel, so validation surfaces
// here rather than in the field chrome.
async function buildLanguageExtension(key?: string): Promise<Extension> {
	const exts: Extension[] = [];
	const lang = await loadLanguage(key);
	if (lang) exts.push(lang);
	if (key === "json") {
		const { jsonParseLinter } = await import("@codemirror/lang-json");
		const { linter, lintGutter } = await import("@codemirror/lint");
		exts.push(lintGutter(), linter(jsonParseLinter()));
	}
	return exts;
}

function buildReadonly(ro: boolean): Extension {
	if (!cmState || !cmView) return [];
	return [cmState.EditorState.readOnly.of(ro), cmView.EditorView.editable.of(!ro)];
}

// Per-variant surface (background + border + focus treatment), mirroring
// frappe-ui's `subtle | outline | ghost` input variants so a code field sits
// flush with the TextInput/Textarea fields around it. The base `theme` owns
// everything else (typography, radius, gutters, tooltips) and deliberately does
// NOT set bg/border, so these fragments are the sole source of surface chrome —
// no precedence fight. Added after `theme` in the extensions array, so they win
// over `basicSetup`'s defaults the same way `theme` already does.
function buildVariant(v?: string): Extension {
	if (!cmView) return [];
	const ring = "0 0 0 2px var(--outline-gray-3, #cbd5e1)";
	const fragments: Record<string, Record<string, Record<string, string>>> = {
		subtle: {
			"&": {
				backgroundColor: "var(--surface-gray-2, #f1f5f9)",
				border: "1px solid var(--surface-gray-2, #e2e8f0)",
			},
			"&.cm-focused": {
				backgroundColor: "var(--surface-white, white)",
				borderColor: "var(--outline-gray-4, #94a3b8)",
				boxShadow: ring,
			},
		},
		outline: {
			"&": {
				backgroundColor: "var(--surface-white, white)",
				border: "1px solid var(--outline-gray-2, #e2e8f0)",
			},
			"&.cm-focused": {
				borderColor: "var(--outline-gray-4, #94a3b8)",
				boxShadow: ring,
			},
		},
		ghost: {
			"&": {
				backgroundColor: "transparent",
				border: "1px solid transparent",
			},
			"&.cm-focused": {
				boxShadow: "none",
			},
		},
	};
	return cmView.EditorView.theme(fragments[v ?? "subtle"] ?? fragments.subtle);
}

onMounted(async () => {
	// SSR guard — no editor without a DOM.
	if (typeof document === "undefined" || !el.value) return;

	cmView = await import("@codemirror/view");
	cmState = await import("@codemirror/state");
	const { basicSetup } = await import("codemirror");
	// `basicSetup` leaves Tab as a focus-move (CodeMirror's a11y default); bind it
	// to indent/dedent so Tab behaves like an editor, not a form field. Escape
	// still releases focus, so keyboard users can tab out via Esc-then-Tab.
	const { indentWithTab } = await import("@codemirror/commands");
	const { EditorView } = cmView;
	const { Compartment, Prec } = cmState;

	languageCompartment = new Compartment();
	readonlyCompartment = new Compartment();
	variantCompartment = new Compartment();

	// lucide `chevron-down`, used as a CSS mask so the fold marker inherits the
	// gutter's `currentColor` (and so flips with the theme) instead of baking a
	// fill. Single-quoted attrs keep it embeddable in this double-quoted string.
	const FOLD_CHEVRON =
		"url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")";

	// Chrome theme. Every color is a frappe-ui `--surface-*` / `--ink-*` token,
	// and those tokens are re-mapped under `[data-theme="dark"]` — so the editor
	// follows the app's light/dark scheme for free (no JS observation, no second
	// theme to swap). The literal fallbacks are the light values, used only when a
	// consumer renders the editor outside the token system.
	const theme = EditorView.theme({
		"&": {
			fontSize: "13px",
			color: "var(--ink-gray-8, #1e293b)",
			borderRadius: "var(--radius-md, 0.5rem)",
			overflow: "hidden",
			// Height cap, driven by the `--cm-max-height` CSS var the component sets
			// from the `maxHeight` prop (`none` when unset, so the editor grows to
			// fit). The inner `.cm-scroller` scrolls once content passes the cap.
			maxHeight: "var(--cm-max-height, none)",
		},
		"&.cm-focused": {
			outline: "none",
		},
		".cm-scroller": {
			overflow: "auto",
		},
		".cm-content": {
			fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
			caretColor: "var(--ink-gray-8, #1e293b)",
			padding: "6px 0",
			minHeight: "4.5rem",
		},
		".cm-cursor, .cm-dropCursor": {
			borderLeftColor: "var(--ink-gray-8, #1e293b)",
		},
		"&.cm-focused .cm-selectionBackground, .cm-selectionBackground, ::selection": {
			backgroundColor: "var(--surface-gray-3, #cbd5e1)",
		},
		".cm-line": {
			padding: "0 6px",
		},
		// Transparent so the gutter inherits whatever surface the active variant
		// paints (gray-2 for `subtle`, white for `outline`, nothing for `ghost`) —
		// otherwise a hardcoded gutter color seams against the filled `subtle`
		// surface. The gray-2 right border stays: invisible on the gray-2 `subtle`
		// fill, a faint separator on the white `outline` surface.
		".cm-gutters": {
			backgroundColor: "transparent",
			borderRight: "1px solid var(--surface-gray-2, #e2e8f0)",
			color: "var(--ink-gray-5, #64748b)",
		},
		// Fold marker. `basicSetup` renders a bare text caret pinned to the
		// cell's top-left; center it and swap the glyph for a masked chevron
		// (inherits the gutter `currentColor`). The marker carries no open/closed
		// class, but its `title` differs — so rotate it to point right when folded.
		".cm-foldGutter .cm-gutterElement": {
			display: "flex",
			alignItems: "center",
			justifyContent: "center",
			padding: "0 2px",
			cursor: "pointer",
		},
		".cm-foldGutter .cm-gutterElement:hover": {
			color: "var(--ink-gray-8, #1e293b)",
		},
		".cm-foldGutter .cm-gutterElement > span": {
			display: "block",
			width: "14px",
			height: "14px",
			fontSize: "0",
			backgroundColor: "currentColor",
			transition: "transform 0.12s ease",
			WebkitMaskImage: FOLD_CHEVRON,
			maskImage: FOLD_CHEVRON,
			WebkitMaskRepeat: "no-repeat",
			maskRepeat: "no-repeat",
			WebkitMaskPosition: "center",
			maskPosition: "center",
			WebkitMaskSize: "14px 14px",
			maskSize: "14px 14px",
		},
		".cm-foldGutter .cm-gutterElement > span[title='Unfold line']": {
			transform: "rotate(-90deg)",
		},
		// `basicSetup` highlights the active line/gutter in a default light blue;
		// override to a subtle espresso gray (token-flipped in dark mode).
		".cm-activeLine": {
			backgroundColor: "var(--surface-gray-2, #f3f3f3)",
		},
		".cm-activeLineGutter": {
			backgroundColor: "var(--surface-gray-2, #f3f3f3)",
			color: "var(--ink-gray-7, #525252)",
		},
		// Autocomplete / hover tooltips (from `basicSetup`) default to a light
		// popup — theme them off `--surface-modal` (the elevated popover surface)
		// so the dropdown follows dark mode instead of flashing white.
		".cm-tooltip": {
			backgroundColor: "var(--surface-modal, white)",
			border: "1px solid var(--surface-gray-3, #cbd5e1)",
			borderRadius: "var(--radius-md, 0.5rem)",
			color: "var(--ink-gray-8, #1e293b)",
			boxShadow: "0 4px 12px rgba(0, 0, 0, 0.12)",
			overflow: "hidden",
		},
		".cm-tooltip-autocomplete > ul": {
			fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
		},
		".cm-tooltip-autocomplete > ul > li": {
			color: "var(--ink-gray-7, #475569)",
			padding: "2px 6px",
		},
		".cm-tooltip-autocomplete > ul > li[aria-selected]": {
			backgroundColor: "var(--surface-gray-3, #e2e8f0)",
			color: "var(--ink-gray-9, #0f172a)",
		},
		".cm-completionIcon": {
			color: "var(--ink-gray-5, #64748b)",
		},
		".cm-completionMatchedText": {
			color: "var(--ink-blue-3)",
			textDecoration: "none",
			fontWeight: "600",
		},
		".cm-completionDetail": {
			color: "var(--ink-gray-5, #64748b)",
			fontStyle: "italic",
		},
	});

	// Syntax highlighting keyed to `--ink-*` tokens so the palette flips with the
	// app theme. `basicSetup` already installs CodeMirror's default (light-tuned)
	// highlight style; layering this at the highest precedence makes it win for
	// every tag we define, and the default only fills the rare gaps we don't.
	const { HighlightStyle, syntaxHighlighting } = await import("@codemirror/language");
	const { tags } = await import("@lezer/highlight");
	const highlightStyle = HighlightStyle.define([
		{
			tag: [tags.keyword, tags.moduleKeyword, tags.controlKeyword],
			color: "var(--ink-blue-3)",
		},
		{
			tag: [tags.string, tags.special(tags.string), tags.regexp],
			color: "var(--ink-green-3)",
		},
		{
			tag: [tags.comment, tags.lineComment, tags.blockComment],
			color: "var(--ink-gray-5)",
			fontStyle: "italic",
		},
		{ tag: [tags.number, tags.bool, tags.null, tags.atom], color: "var(--ink-amber-3)" },
		{ tag: [tags.typeName, tags.className, tags.namespace], color: "var(--ink-amber-3)" },
		{
			tag: [
				tags.function(tags.variableName),
				tags.function(tags.propertyName),
				tags.labelName,
			],
			color: "var(--ink-blue-3)",
		},
		{ tag: [tags.propertyName, tags.attributeName], color: "var(--ink-red-3)" },
		{ tag: [tags.tagName, tags.angleBracket], color: "var(--ink-red-3)" },
		{
			tag: [tags.operator, tags.punctuation, tags.separator, tags.bracket],
			color: "var(--ink-gray-6)",
		},
		{
			tag: [tags.variableName, tags.definition(tags.variableName)],
			color: "var(--ink-gray-8)",
		},
		{ tag: tags.meta, color: "var(--ink-gray-5)" },
		{ tag: [tags.link, tags.url], color: "var(--ink-blue-3)", textDecoration: "underline" },
		{ tag: tags.heading, color: "var(--ink-blue-3)", fontWeight: "bold" },
		{ tag: tags.strong, fontWeight: "bold" },
		{ tag: tags.emphasis, fontStyle: "italic" },
		{ tag: tags.strikethrough, textDecoration: "line-through" },
		{ tag: tags.invalid, color: "var(--ink-red-4)" },
	]);
	const highlight = Prec.highest(syntaxHighlighting(highlightStyle));

	const updateListener = EditorView.updateListener.of((update) => {
		if (update.docChanged) {
			if (!syncingFromProp) emit("update:modelValue", update.state.doc.toString());
			// Content height may have changed (capped scroller won't trigger the
			// ResizeObserver, so re-check here on every doc edit).
			measureOverflow();
		}
	});

	// Blur is the commit point (mirrors the typed-field contract).
	const blurHandler = EditorView.domEventHandlers({
		blur: () => {
			if (view) emit("change", view.state.doc.toString());
		},
	});

	// Escape releases focus. `indentWithTab` rebinds Tab to indent, which would
	// otherwise trap keyboard users inside the editor with no way out (WCAG
	// 2.1.2). Escape blurs the content DOM so they can Tab on to the next field —
	// Esc-then-Tab, the standard CodeMirror keyboard-trap escape hatch.
	const escapeHandler = EditorView.domEventHandlers({
		keydown: (e, v) => {
			if (e.key === "Escape") {
				v.contentDOM.blur();
				return true;
			}
			return false;
		},
	});

	const extensions: Extension[] = [
		basicSetup,
		cmView.keymap.of([indentWithTab]),
		escapeHandler,
		languageCompartment.of(await buildLanguageExtension(props.language)),
		readonlyCompartment.of(buildReadonly(!!props.readonly)),
		updateListener,
		blurHandler,
		theme,
		variantCompartment.of(buildVariant(props.variant)),
		highlight,
	];
	if (props.placeholder) {
		extensions.push(cmView.placeholder(props.placeholder));
	}

	// Bail if the component unmounted while the dynamic imports above were in
	// flight — otherwise we'd create a view + observer that `onBeforeUnmount`
	// already ran past and nothing would ever destroy.
	if (destroyed || !el.value) return;

	view = new EditorView({
		doc: props.modelValue ?? "",
		extensions,
		parent: el.value,
	});

	applyMaxHeight();
	// Catches overflow changes the doc-edit path misses: wrapping reflow on width
	// change, and the cap being applied/removed. Fires once on observe for the
	// initial measurement.
	if (typeof ResizeObserver !== "undefined") {
		overflowObserver = new ResizeObserver(() => measureOverflow());
		overflowObserver.observe(view.scrollDOM);
	}
});

// Sync external `modelValue` changes into the view. This is also what makes the
// wrapper's JSON pretty-print visible: when it rewrites the value on commit, this
// dispatches the reformatted string back into the editor.
//
// Rather than replacing the whole doc (which would reset the caret to the end,
// collapse the selection, jump the scroll, and abort IME composition), we diff
// off the common prefix/suffix and change only the differing middle. CodeMirror
// then maps the existing selection through that change, so an unchanged caret
// stays put — important when a consumer transforms the value live, not just on
// the unfocused blur/pretty-print path.
watch(
	() => props.modelValue,
	(val) => {
		if (!view) return;
		const current = view.state.doc.toString();
		const next = val ?? "";
		if (next === current) return;

		// Longest common prefix.
		let from = 0;
		const max = Math.min(current.length, next.length);
		while (from < max && current[from] === next[from]) from++;
		// Longest common suffix (not overlapping the prefix on either side).
		let curEnd = current.length;
		let nextEnd = next.length;
		while (curEnd > from && nextEnd > from && current[curEnd - 1] === next[nextEnd - 1]) {
			curEnd--;
			nextEnd--;
		}

		syncingFromProp = true;
		view.dispatch({
			changes: { from, to: curEnd, insert: next.slice(from, nextEnd) },
		});
		syncingFromProp = false;
	}
);

// Swap the language (and JSON linter) without recreating the view. The extension
// build is async (it dynamic-imports the `@codemirror/lang-*` package), so a fast
// A→B switch races two builds; the monotonic `langSeq` token drops a stale build
// whose import resolves after a newer one, so the latest `props.language` always
// wins regardless of import-resolution order.
let langSeq = 0;
watch(
	() => props.language,
	async (key) => {
		const seq = ++langSeq;
		const ext = await buildLanguageExtension(key);
		if (!view || !languageCompartment || seq !== langSeq) return;
		view.dispatch({
			effects: languageCompartment.reconfigure(ext),
		});
	}
);

watch(
	() => props.readonly,
	(ro) => {
		if (!view || !readonlyCompartment) return;
		view.dispatch({ effects: readonlyCompartment.reconfigure(buildReadonly(!!ro)) });
	}
);

// Swap the surface variant without recreating the view.
watch(
	() => props.variant,
	(v) => {
		if (!view || !variantCompartment) return;
		view.dispatch({ effects: variantCompartment.reconfigure(buildVariant(v)) });
	}
);

// Re-cap on `maxHeight` change (the expand/collapse toggle drives this).
watch(
	() => props.maxHeight,
	() => applyMaxHeight()
);

onBeforeUnmount(() => {
	destroyed = true;
	overflowObserver?.disconnect();
	overflowObserver = null;
	if (view) {
		view.destroy();
		view = null;
	}
});
</script>
