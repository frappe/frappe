<template>
	<!-- A single, persistent CodeEditor instance across all layouts: the `split`
	     grid adds a side column for the preview, while `stacked` renders the
	     preview *below* the editor and `editor` leaves it full-width with none.
	     Keeping one instance (rather than one per branch) means crossing the
	     split-width threshold no longer remounts the editor and discards its undo
	     history, focus, and scroll. The preview is always live — there is no
	     write/preview mode switch; the editor is never hidden. -->
	<div ref="root" :class="layout === 'split' ? 'grid grid-cols-2 items-start gap-3' : ''">
		<!-- Writer cell. The inner `relative` box anchors the floating Expand/
		     Collapse pill to the *editor* (not the whole cell). The stacked preview
		     is a sibling *below* the labelled group so the editor's bottom fade
		     covers only the code, never the help text or the preview. -->
		<div>
			<!-- `space-y-1.5` is the gap frappe-ui's own labelled inputs put between
			     label, control and description. -->
			<div class="space-y-1.5">
				<!-- The v1 CodeEditor is renderless and draws no chrome at all, so
				     the label, the required marker and the description belong to the
				     field. `forId` is omitted everywhere below: the control is
				     CodeMirror's contenteditable, which `<label for>` cannot target —
				     the accessible name reaches it through `contentAttributes`. -->
				<InputLabel
					v-if="field.label"
					:id="labelId"
					:label="field.label"
					:required="field.reqd"
					:disabled="field.readOnly"
				/>
				<div class="relative" :data-readonly="field.readOnly ? 'true' : undefined">
					<CodeEditor
						:modelValue="value"
						:extensions="extensions"
						:editable="!field.readOnly"
						@update:modelValue="onInput"
						@change="onCommit"
					>
						<!-- The box. Collapsed it is capped at `max-h-54` (13.5rem);
						     expanded the cap is dropped entirely. frappe-ui ships the
						     cap rule at zero specificity, so this class always wins. -->
						<CodeEditorContent
							class="code-fade"
							:class="expanded ? undefined : 'max-h-54'"
							@overflow="overflowing = $event"
						/>
					</CodeEditor>
					<!-- Expand/collapse — floats centered over the editor's bottom edge,
					     sitting on the fade so it reads as "there's more below". Shown
					     only when content overflows the collapsed cap (or while expanded,
					     so it can be re-collapsed). A labelled outline pill (solid white
					     surface) stays legible over the faded code beneath it. -->
					<Button
						v-if="showExpand"
						class="absolute bottom-2 left-1/2 z-10 -translate-x-1/2"
						variant="outline"
						size="sm"
						:iconLeft="expanded ? 'lucide-chevrons-up' : 'lucide-chevrons-down'"
						:label="expanded ? 'Collapse' : 'Expand'"
						@click="expanded = !expanded"
					/>
				</div>
				<InputDescription
					v-if="field.description"
					:id="descriptionId"
					:description="field.description"
					:disabled="field.readOnly"
				/>
			</div>
			<!-- Narrow `stacked` layout: a live preview always sits below the editor
			     (the wide `split` layout shows it as a side column instead). It's
			     wrapped in a disclosure so it can be collapsed to reclaim vertical
			     space — always-on means it would otherwise double the field height. -->
			<div v-if="layout === 'stacked'" class="mt-3">
				<!-- Disclosure header. frappe-ui has no collapsible/disclosure
				     primitive, so the clickable wrapper is a deliberate plain
				     <button>; the "Preview" text reuses frappe-ui's InputLabel so its
				     typography matches the editor's own label, and the chevron shows
				     open vs. collapsed state. -->
				<button
					type="button"
					class="flex items-center gap-1"
					@click="previewOpen = !previewOpen"
				>
					<span
						:class="previewOpen ? 'lucide-chevron-down' : 'lucide-chevron-right'"
						class="size-3.5 text-ink-gray-7"
						aria-hidden="true"
					/>
					<InputLabel
						:id="previewLabelId"
						label="Preview"
						class="text-p-sm-medium text-ink-gray-7"
					/>
				</button>
				<CodePreview
					v-show="previewOpen"
					:modelValue="value"
					:language="languageKey"
					class="mt-1 min-h-18 rounded-4 border border-outline-gray-2 p-3"
				/>
			</div>
		</div>
		<!-- Wide `split` layout: writer + preview side-by-side. The preview column
		     gets its own "Preview" header (only when the writer has a label, so the
		     two columns either both have a header row or neither does) so its top
		     lines up with the editor instead of floating above the label. -->
		<div v-if="layout === 'split'" class="space-y-1.5">
			<InputLabel
				v-if="field.label"
				:id="previewLabelId"
				label="Preview"
				class="text-p-sm-medium text-ink-gray-7"
			/>
			<CodePreview
				:modelValue="value"
				:language="languageKey"
				class="min-h-18 rounded-4 border border-outline-gray-2 p-3"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
// Field wrapper for the code-family fieldtypes (JSON / Markdown Editor /
// HTML Editor / Code). Composes frappe-ui's v1 code-editor family with the local
// `CodePreview`, deriving the language from the field. The value stays a string
// in `doc` (Frappe JSON/Code fields store strings) — the contract is unchanged.
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, useId, watch } from "vue";
import { Button } from "frappe-ui";
import { InputLabel, InputDescription } from "frappe-ui/experimental";
import { CodeEditor, CodeEditorContent, CodeKit, loadLanguage } from "frappe-ui/code-editor";
import { EditorView } from "@codemirror/view";
import type { Extension } from "@codemirror/state";
import CodePreview from "./CodePreview.vue";
import { fieldtypeToLanguage } from "./fieldtypeToLanguage";
import type { FieldComponentEmits, FieldComponentProps } from "./types";

const props = withDefaults(
	defineProps<
		FieldComponentProps & {
			/**
			 * Writer/preview arrangement. `"auto"` (default) picks responsively —
			 * `split` (preview side-by-side) in a wide column, `stacked` (live
			 * preview below the editor) in a narrow one. An explicit `"split"` /
			 * `"stacked"` / `"editor"` forces that arrangement; it's still clamped
			 * to `editor` for fieldtypes with no preview (JSON / Code). Settable
			 * from a schema via the field's `ui.props` overlay.
			 */
			view?: "auto" | "editor" | "split" | "stacked";
		}
	>(),
	{ view: "auto" }
);
const emit = defineEmits<FieldComponentEmits>();

// Value stays a string; LinkField-style get (the editor owns its own buffer, so
// no setter — commits flow through `onInput`/`onCommit`).
const value = computed<string>(() => props.modelValue ?? "");

const languageKey = computed(() => fieldtypeToLanguage(props.field));

// `loadLanguage` code-splits the ten CodeMirror grammars, so the extension lands
// after mount. `extensions` is reactive, so it is applied with one reconfigure:
// no remount, and the document, selection and undo history all survive. A key the
// map doesn't know (`plain`) resolves to `null` — plain text, no highlighting.
const languageExtension = shallowRef<Extension | null>(null);
let languageRequest = 0;

watch(
	languageKey,
	(key) => {
		const request = ++languageRequest;
		loadLanguage(key)
			.then((extension) => {
				// A slow earlier load must not land on top of a newer language.
				if (request === languageRequest) languageExtension.value = extension;
			})
			.catch((error) => {
				// The throw names the `@codemirror/lang-*` package to install.
				if (request === languageRequest) languageExtension.value = null;
				console.error(error);
			});
	},
	{ immediate: true }
);

// Built outside the `extensions` computed: a kit rebuilt on every recompute is a
// new extension identity, and the reconfigure takes the undo history with it.
const kit = computed(() =>
	props.field.placeholder ? CodeKit.configure({ placeholder: props.field.placeholder }) : CodeKit
);

// Stable ids for the InputLabel/InputDescription elements (frappe-ui's labeling
// primitives require an explicit id). The split and stacked layouts never render
// together, so the preview label can share one id.
const labelId = useId();
const descriptionId = useId();
const previewLabelId = useId();

// The family sets no ARIA of its own, and `<label for>` cannot target a
// contenteditable, so the field pushes its own labelling onto CodeMirror's
// content element. Recomputes only when the field's meta changes.
const contentAttributes = computed(() => {
	const attrs: Record<string, string> = {};
	if (props.field.label) attrs["aria-labelledby"] = labelId;
	if (props.field.description) attrs["aria-describedby"] = descriptionId;
	if (props.field.reqd) attrs["aria-required"] = "true";
	return EditorView.contentAttributes.of(attrs);
});

const extensions = computed<Extension[]>(() => {
	const list: Extension[] = [kit.value];
	if (languageExtension.value) list.push(languageExtension.value);
	list.push(contentAttributes.value);
	return list;
});

// Only Markdown / HTML have a meaningful preview; JSON / Code never mount one.
const hasPreview = computed(
	() => languageKey.value === "markdown" || languageKey.value === "html"
);
// The stacked preview can be collapsed to reclaim vertical space; open by default
// so the live preview is visible without a click.
const previewOpen = ref(true);

// Responsive layout: when `view` is `"auto"`, a previewable field shows the
// preview side-by-side in a wide column and stacks it below the editor in a narrow
// one. Width is observed on the wrapper so the choice tracks the real rendered
// space (form column, modal, split view), not the viewport.
const SPLIT_MIN_WIDTH = 640;
const root = ref<HTMLElement | null>(null);
const isWide = ref(false);
let observer: ResizeObserver | null = null;

const layout = computed<"editor" | "split" | "stacked">(() => {
	// Nothing to preview → always the bare editor, even if `view` asks otherwise.
	if (!hasPreview.value) return "editor";
	if (props.view !== "auto") return props.view;
	return isWide.value ? "split" : "stacked";
});

// Expand/collapse: the editor is capped at 13.5rem (`max-h-54`) until expanded.
// The pill only appears once the content overflows the cap (CodeEditorContent
// reports this through `overflow`), or while expanded — expanding drops the cap,
// which fires `overflow(false)`, so a pill bound to `overflowing` alone would take
// the way back with it.
const expanded = ref(false);
const overflowing = ref(false);
const showExpand = computed(() => overflowing.value || expanded.value);

// Only "auto" needs the width measurement; a forced `view` skips the observer
// entirely.
function attachObserver() {
	if (observer || typeof ResizeObserver === "undefined" || !root.value) return;
	observer = new ResizeObserver((entries) => {
		isWide.value = entries[0].contentRect.width >= SPLIT_MIN_WIDTH;
	});
	observer.observe(root.value);
}

function detachObserver() {
	observer?.disconnect();
	observer = null;
}

// Attach on mount (when `root` is bound) for the initial "auto"; the watch then
// starts/stops it as `view` flips to/from "auto" at runtime. It must NOT be
// `immediate` — an immediate callback runs during setup, before `root` exists.
onMounted(() => {
	if (props.view === "auto") attachObserver();
});

watch(
	() => props.view === "auto",
	(auto) => (auto ? attachObserver() : detachObserver())
);

onBeforeUnmount(detachObserver);

// Live edits keep `doc` reactive while typing.
function onInput(v: string) {
	emit("update:modelValue", v);
}

// Commit. `change` fires on a blur that follows an edit, so a focus-and-leave
// commits nothing. JSON is pretty-printed here; on parse failure the raw text is
// kept. The rewritten value flows back in through `modelValue`, which the engine
// applies as a minimal diff — caret, scroll and any in-flight IME survive it.
function onCommit(v: string) {
	let out = v;
	if (props.field.fieldtype === "JSON") {
		try {
			out = JSON.stringify(JSON.parse(v), null, 2);
		} catch {
			out = v;
		}
	}
	emit("update:modelValue", out);
	emit("change", out);
}
</script>

<style scoped>
/* A read-only field takes the quiet non-control fill, which is what every other
   disabled input in the system uses. v1 dropped the `disabled` prop for
   `editable`, and `editable` alone changes nothing visual — the surface is the
   consumer's, set through the `--code-bg` hook on an ancestor. */
[data-readonly="true"] {
	--code-bg: var(--surface-gray-1);
}

/* Collapsed *and* overflowing, the box fades its content out at the bottom so the
   floating Expand pill reads as "there's more below". `data-overflowing` is part
   of CodeEditorContent's public surface, and expanding drops the cap — the
   attribute clears itself, so nothing here needs a JS toggle. Masking fades the
   real pixels, so it holds on any background and in any focus state. */
.code-fade[data-overflowing="true"] {
	-webkit-mask-image: linear-gradient(to bottom, #000 60%, transparent);
	mask-image: linear-gradient(to bottom, #000 60%, transparent);
}
</style>
