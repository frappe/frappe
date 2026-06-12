<template>
	<div ref="root" class="space-y-1.5">
		<!-- Field chrome (label / required indicator), mirroring the textarea field.
		     Rendered whenever there's a label OR a control to show (the toggle or the
		     expand/collapse action), so a label-less field still gets its controls. -->
		<div
			v-if="field.label || layout === 'toggle' || showExpand"
			class="flex items-center"
			:class="field.label ? 'justify-between' : 'justify-end'"
		>
			<label v-if="field.label" class="block text-xs text-ink-gray-5">
				{{ field.label }}
				<span v-if="field.reqd" class="text-ink-red-8">*</span>
			</label>
			<div class="flex gap-1">
				<!-- Write/Preview toggle — only in the narrow `toggle` layout. When the
				     column is wide enough we show writer + preview side-by-side instead,
				     so the toggle is unnecessary. The primitives stay agnostic; the
				     split-vs-toggle choice is a wrapper-level, width-driven detail.
				     A single icon button flips between the two: the icon/tooltip show
				     the mode you'd switch *to* (eye → preview, pencil → write). -->
				<Button
					v-if="layout === 'toggle'"
					variant="ghost"
					size="sm"
					:icon="mode === 'write' ? 'lucide-eye' : 'lucide-pencil'"
					:tooltip="mode === 'write' ? 'Preview' : 'Write'"
					@click="mode = mode === 'write' ? 'preview' : 'write'"
				/>
				<!-- Expand/collapse — only when the editor's content overflows the
				     collapsed cap (or is already expanded, so it can be re-collapsed). -->
				<Button
					v-if="showExpand"
					variant="ghost"
					size="sm"
					:icon="expanded ? 'lucide-chevrons-up' : 'lucide-chevrons-down'"
					:tooltip="expanded ? 'Collapse' : 'Expand'"
					@click="expanded = !expanded"
				/>
			</div>
		</div>

		<!-- A single, persistent CodeEditor instance across all three layouts: the
		     `split` grid only adds a column for the preview, while `toggle`/`editor`
		     leave it full-width. Keeping one instance (rather than one per branch)
		     means crossing the split-width threshold no longer remounts the editor
		     and discards its undo history, focus, and scroll. The writer is hidden —
		     not unmounted — when the narrow toggle shows the preview. -->
		<div :class="layout === 'split' ? 'grid grid-cols-2 gap-3' : ''">
			<CodeEditor
				v-show="layout !== 'toggle' || mode === 'write'"
				:modelValue="value"
				:language="language"
				:readonly="field.readOnly"
				:placeholder="field.placeholder"
				:maxHeight="expanded ? undefined : COLLAPSED_HEIGHT"
				@update:modelValue="onInput"
				@change="onCommit"
				@overflow="overflowing = $event"
			/>
			<CodePreview
				v-if="hasPreview && (layout === 'split' || mode === 'preview')"
				:modelValue="value"
				:language="language"
				class="min-h-[4.5rem] rounded-md border border-surface-gray-2 p-3"
			/>
		</div>

		<p v-if="field.description" class="text-xs text-ink-gray-5">
			{{ field.description }}
		</p>
	</div>
</template>

<script setup lang="ts">
// Field wrapper for the code-family fieldtypes (JSON / Markdown Editor /
// HTML Editor / Code). Composes the `CodeEditor` writer with the `CodePreview`
// primitive, deriving the language from the field. The value stays a string in
// `doc` (Frappe JSON/Code fields store strings) — the contract is unchanged.
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Button } from "frappe-ui";
import { CodeEditor, CodePreview, fieldtypeToLanguage } from "../../CodeEditor";
import type { FieldComponentEmits, FieldComponentProps } from "../types";

const props = withDefaults(
	defineProps<
		FieldComponentProps & {
			/**
			 * Writer/preview arrangement. `"auto"` (default) picks responsively —
			 * `split` (side-by-side) in a wide column, `toggle` (Write/Preview
			 * buttons) in a narrow one. An explicit `"split"` / `"toggle"` /
			 * `"editor"` forces that arrangement; it's still clamped to `editor`
			 * for fieldtypes with no preview (JSON / Code). Settable from a schema
			 * via the field's `ui.props` overlay.
			 */
			view?: "auto" | "editor" | "split" | "toggle";
		}
	>(),
	{ view: "auto" }
);
const emit = defineEmits<FieldComponentEmits>();

// Value stays a string; LinkField-style get (the editor owns its own buffer, so
// no setter — commits flow through `onInput`/`onCommit`).
const value = computed<string>(() => props.modelValue ?? "");

const language = computed(() => fieldtypeToLanguage(props.field));

// Only Markdown / HTML have a meaningful preview; JSON / Code never mount one.
const hasPreview = computed(() => language.value === "markdown" || language.value === "html");
const mode = ref<"write" | "preview">("write");

// Responsive layout: when `view` is `"auto"`, a previewable field shows writer +
// preview side-by-side in a wide column and falls back to a Write/Preview toggle
// in a narrow one. Width is observed on the wrapper so the choice tracks the real
// rendered space (form column, modal, split view), not the viewport.
const SPLIT_MIN_WIDTH = 640;
const root = ref<HTMLElement | null>(null);
const isWide = ref(false);
let observer: ResizeObserver | null = null;

const layout = computed<"editor" | "split" | "toggle">(() => {
	// Nothing to preview → always the bare editor, even if `view` asks otherwise.
	if (!hasPreview.value) return "editor";
	if (props.view !== "auto") return props.view;
	return isWide.value ? "split" : "toggle";
});

// Expand/collapse: the editor is capped at COLLAPSED_HEIGHT until expanded. The
// toggle only appears once the content overflows the cap (the editor reports
// this via its `overflow` emit), or while expanded so it can be collapsed back.
// The writer is hidden in the toggle layout's preview mode — no point offering
// expand there.
const COLLAPSED_HEIGHT = "13.5rem";
const expanded = ref(false);
const overflowing = ref(false);
const writerVisible = computed(() => layout.value !== "toggle" || mode.value === "write");
const showExpand = computed(() => writerVisible.value && (overflowing.value || expanded.value));

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
