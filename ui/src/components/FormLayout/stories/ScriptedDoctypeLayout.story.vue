<!--
  Meta scripting against **real doctype meta**. Unlike MetaScript.story (which
  scripts a hand-written base), this fetches `ToDo`'s meta via the standard path
  and runs the ops through `useScriptedLayout(doctype, ops)`:

    useDoctypeLayout('ToDo') → applyMetaScript(ops) → FormLayout

  Two distinct scripting flavours are demoed side by side:

  • META scripting (flavour B) — `ops` is a per-doc-reactive `computed` that reads
    the live doc (architecture §8.4-reactive), so "relabel Description when priority
    is High" / "hide Date when status is Closed" re-evaluate as the user edits.
    Operates on **meta** (label/hidden/…) via `applyMetaScript`.

  • BEHAVIOUR scripting (flavour A) — `@change(fieldname, value)` is the **commit
    funnel** (`CommitKey`). On commit it runs a per-field trigger that mutates the
    **doc** (sets sibling values), Frappe `frm.trigger`-style. The parent owns `doc`
    via `v-model:doc`, so trigger writes flow straight back and stay reactive.

  Both reach a deeply-rendered field with **no** new prop/provide/event on
  `FormLayout` — meta via the schema seam, behaviour via the existing `@change`.
-->
<template>
	<div class="p-6 max-w-3xl">
		<label class="flex items-center gap-2 text-sm text-ink-gray-7 mb-4">
			<input type="checkbox" v-model="scriptEnabled" />
			Apply scripts (meta + behaviour)
		</label>

		<div v-if="loading" class="text-ink-gray-6">Loading meta…</div>
		<div v-else-if="error" class="text-ink-red-4">{{ errorMessage }}</div>
		<FormLayout v-else v-model:doc="doc" :layout="layout" @change="onChange" />

		<div class="mt-6 grid grid-cols-2 gap-6 text-xs text-ink-gray-6">
			<div>
				<p class="font-medium mb-1">Meta ops (recomputed from the doc):</p>
				<pre>{{ ops.length ? ops : "(none)" }}</pre>
			</div>
			<div>
				<p class="font-medium mb-1">doc (mutated by @change triggers):</p>
				<pre>{{ doc }}</pre>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import FormLayout from "../FormLayout.vue";
import { useScriptedLayout } from "../useScriptedLayout";
import type { MetaOp } from "../applyMetaScript";

const props = withDefaults(defineProps<{ doctype?: string }>(), {
	doctype: "ToDo",
});

const doc = reactive<Record<string, any>>({ status: "Open", priority: "Medium" });
const scriptEnabled = ref(true);

/**
 * The "script" — a doc-conditional evaluator. Returns the `MetaOp[]` that should
 * apply for the *current* doc state. Because it's called from a `computed` that
 * reads `doc`, changing `priority`/`status` in the form re-runs it and the layout
 * re-renders. Stand-in for the future server-stored script's evaluation.
 */
function evaluate(d: Record<string, any>): MetaOp[] {
	const ops: MetaOp[] = [];

	// Rule 1 — "update title": when priority is High, flag the Description label.
	ops.push({
		op: "setFieldProperty",
		fieldname: "description",
		prop: "label",
		value: d.priority === "High" ? "Description — URGENT" : "Description",
	});

	// Rule 2 — "hide a field when another is set": a Closed ToDo hides Priority
	// (its priority is moot once closed). Date stays visible so the @change trigger
	// below — which stamps Date on close — is observable.
	if (d.status === "Closed") {
		ops.push({ op: "hideField", fieldname: "priority" });
	}

	return ops;
}

const ops = computed<MetaOp[]>(() => (scriptEnabled.value ? evaluate(doc) : []));

const { layout, loading, error } = useScriptedLayout(props.doctype, ops);
const errorMessage = computed(() =>
	error.value instanceof Error ? error.value.message : String(error.value)
);

/**
 * Behaviour script (flavour A) — per-field on-**commit** triggers, keyed by
 * fieldname. Each receives the live `doc` (mutable) plus the committed value, and
 * may set sibling fields. Stand-in for the future server-stored controller's
 * methods; runs only on commit (blur / selection), not per keystroke.
 */
const triggers: Record<string, (d: Record<string, any>, value: any) => void> = {
	// Closing a ToDo stamps today's date if none is set.
	status(d, value) {
		if (value === "Closed" && !d.date) {
			d.date = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
		}
	},
	// High priority paints the colour swatch red (a cross-field value write).
	priority(d, value) {
		if (value === "High") d.color = "#ef4444";
	},
};

function onChange(fieldname: string, value: any) {
	if (!scriptEnabled.value) return;
	triggers[fieldname]?.(doc, value);
}
</script>
