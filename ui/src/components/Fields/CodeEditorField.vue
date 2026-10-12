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
		     Collapse pill to the *editor* (not the whole cell). The description and
		     the stacked preview are rendered as siblings *below* this box (rather
		     than inside it) so the editor's bottom fade covers only the code,
		     never the help text or the preview. -->
		<div>
			<!-- frappe-ui's code editor is renderless; the label and every other chrome is drawn here. -->
			<InputLabel
				v-if="field.label"
				:id="labelId"
				:label="field.label"
				:required="field.reqd"
			/>
			<div class="relative" :class="{ 'mt-1': field.label }">
				<CodeEditor
					:modelValue="value"
					:extensions="extensions"
					:editable="!field.readOnly"
					@update:modelValue="onInput"
					@change="onCommit"
				>
					<!-- `--code-max-height` on the part drives both the clip and the `overflow` signal. -->
					<CodeEditorContent
						:class="{
							'code-collapsed': !expanded,
							'code-fade': showExpand && !expanded,
						}"
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
			<!-- Description, split out of CodeEditor so the fade above never touches
			     it. Uses frappe-ui's InputDescription so the markup/spacing match
			     every other field's help text. -->
			<InputDescription
				v-if="field.description"
				:id="descriptionId"
				:description="field.description"
				class="mt-1"
			/>
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
					:language="language"
					class="mt-1 min-h-[4.5rem] rounded-5 border border-outline-gray-1 p-3"
				/>
			</div>
		</div>
		<!-- Wide `split` layout: writer + preview side-by-side. The preview column
		     gets its own "Preview" header (only when the writer has a label, so the
		     two columns either both have a header row or neither does) so its top
		     lines up with the editor instead of floating above the label. -->
		<div v-if="layout === 'split'" class="space-y-1">
			<!-- Pane header — frappe-ui's InputLabel (no `forId`: there's no control
			     to bind, it just matches CodeEditor's own label so the columns align). -->
			<InputLabel
				v-if="field.label"
				:id="previewLabelId"
				label="Preview"
				class="text-p-sm-medium text-ink-gray-7"
			/>
			<CodePreview
				:modelValue="value"
				:language="language"
				class="min-h-[4.5rem] rounded-5 border border-outline-gray-1 p-3"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
// Field wrapper for the code-family fieldtypes (JSON / Markdown Editor /
// HTML Editor / Code). Composes frappe-ui's renderless `CodeEditor` with the local
// `CodePreview`, deriving the language from the field. The value stays a string in
// `doc` (Frappe JSON/Code fields store strings) — the contract is unchanged.
import type { Extension } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, useId, watch } from "vue";
import { Button } from "frappe-ui";
import { CodeEditor, CodeEditorContent, CodeKit, loadLanguage } from "frappe-ui/code-editor";
import { InputDescription, InputLabel } from "frappe-ui/experimental";
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

const language = computed(() => fieldtypeToLanguage(props.field));

// Configured outside `extensions`, so the array's members stay stable between renders.
// Completion stays off: the field supplies no sources.
const kit = computed(() =>
	CodeKit.configure({
		// The kit ships line numbers off; the field drew them before rc.1.
		lineNumbers: {},
		autocompletion: false,
		placeholder: props.field.placeholder || false,
	})
);

// The grammar loads after mount and lands through the reactive `extensions`; an answer for
// a language the field has since left is dropped.
const languageExtension = shallowRef<Extension | null>(null);
watch(
	language,
	async (key) => {
		const wanted = key;
		let loaded: Extension | null = null;
		try {
			loaded = await loadLanguage(key);
		} catch (error) {
			// The message names the package to install.
			console.error(error);
		}
		if (language.value === wanted) languageExtension.value = loaded;
	},
	{ immediate: true }
);

// JSON fields lint as before: a parse error marks the line. The lint packages load only
// for a JSON field; frappe-ui's vite plugin stubs an absent one with a throw.
const lintExtensions = shallowRef<Extension[]>([]);
watch(
	() => props.field.fieldtype === "JSON",
	async (wanted) => {
		if (!wanted) {
			lintExtensions.value = [];
			return;
		}
		try {
			const [{ linter, lintGutter }, { jsonParseLinter }] = await Promise.all([
				import("@codemirror/lint"),
				import("@codemirror/lang-json"),
			]);
			if (props.field.fieldtype === "JSON") {
				lintExtensions.value = [lintGutter(), linter(jsonParseLinter())];
			}
		} catch (error) {
			console.error(error);
		}
	},
	{ immediate: true }
);

// The label and description are linked to CodeMirror's content element, as the old
// labelled editor did through the same facet.
const contentAttributes = computed(() =>
	EditorView.contentAttributes.of({
		"aria-labelledby": props.field.label ? labelId : "",
		"aria-describedby": props.field.description ? descriptionId : "",
		"aria-required": props.field.reqd ? "true" : "false",
	})
);

const extensions = computed<Extension[]>(() => {
	const list: Extension[] = [kit.value, contentAttributes.value];
	if (languageExtension.value) list.push(languageExtension.value);
	list.push(...lintExtensions.value);
	return list;
});

// Only Markdown / HTML have a meaningful preview; JSON / Code never mount one.
const hasPreview = computed(() => language.value === "markdown" || language.value === "html");
// The stacked preview can be collapsed to reclaim vertical space; open by default
// so the live preview is visible without a click.
const previewOpen = ref(true);

// Stable ids for the InputLabel/InputDescription elements (frappe-ui's labeling
// primitives require an explicit id). The split and stacked layouts never render
// together, so the preview label can share one id.
const labelId = useId();
const descriptionId = useId();
const previewLabelId = useId();

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

// Expand/collapse: the editor is capped by `.code-collapsed` until expanded. The
// pill only appears once the content overflows the cap (the editor reports this
// via its `overflow` emit), or while expanded so it can be collapsed back. The
// editor is always visible (no mode switch), so this tracks the cap alone.
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

// Commit (blur). JSON is pretty-printed at the component edge; on parse failure
// the raw text is kept. The rewritten value flows back into the editor via its
// `modelValue` watch.
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
/* The cap a collapsed editor is held to. `--code-max-height` is the part's own hook, so
   the height drives both the clip and the `overflow` signal the Expand pill listens to. */
.code-collapsed {
	--code-max-height: 13.5rem;
}

/* Collapsed editors fade their content out at the bottom so the floating Expand
   pill reads as "there's more below". Masking the scroller (rather than overlaying
   a solid gradient) fades the actual pixels, so it works regardless of the editor's
   background or focus state. `:deep` reaches CodeMirror's scroller, which is
   rendered inside the `CodeEditorContent` part. */
.code-fade :deep(.cm-scroller) {
	-webkit-mask-image: linear-gradient(to bottom, #000 60%, transparent);
	mask-image: linear-gradient(to bottom, #000 60%, transparent);
}
</style>
