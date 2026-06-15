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

  • BEHAVIOUR scripting (flavour A) — a per-field commit trigger is attached as
    that field node's **`ui.on.change`** (the schema-driven overlay). On commit it
    mutates the **doc** (sets sibling values), Frappe `frm.trigger`-style. The
    parent owns `doc` via `v-model:doc`, so trigger writes flow straight back and
    stay reactive. `FormLayout` emits nothing; the handler is baked into the layout.

  Both reach a deeply-rendered field with **no** prop/provide/event on
  `FormLayout` — meta via the schema seam, behaviour via the field's `ui.on`. In
  the real product this overlay is produced by a `scriptDecorator` at build time
  (`buildLayoutFromMeta`'s `decorate` hook); here we overlay it onto the built tree
  since `useScriptedLayout` doesn't expose that seam.
-->
<template>
	<div class="p-6 max-w-3xl">
		<label class="flex items-center gap-2 text-sm text-ink-gray-7 mb-4">
			<input type="checkbox" v-model="scriptEnabled" />
			Apply scripts (meta + behaviour)
		</label>

		<div v-if="loading" class="text-ink-gray-6">Loading meta…</div>
		<div v-else-if="error" class="text-ink-red-8">{{ errorMessage }}</div>
		<FormLayout v-else v-model:doc="doc" :layout="layout" />

		<div class="mt-6 grid grid-cols-2 gap-6 text-xs text-ink-gray-6">
			<div>
				<p class="font-medium mb-1">Meta ops (recomputed from the doc):</p>
				<pre>{{ ops.length ? ops : "(none)" }}</pre>
			</div>
			<div>
				<p class="font-medium mb-1">doc (mutated by ui.on.change triggers):</p>
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
import type { FormLayoutSchema } from "../types";

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

const { layout: metaLayout, loading, error } = useScriptedLayout(props.doctype, ops);
const errorMessage = computed(() =>
	error.value instanceof Error ? error.value.message : String(error.value)
);

// Overlay behaviour triggers as `ui.on.change` on each scripted field. Stand-in
// for the build-time `scriptDecorator`: maps the layout tree, merging a commit
// handler onto fields named in `triggers` (existing `ui.on.change` handlers are
// preserved so overlays compose). Gated by the same `scriptEnabled` toggle.
function withBehaviour(schema: FormLayoutSchema): FormLayoutSchema {
	return schema.map((tab) => ({
		...tab,
		sections: tab.sections.map((section) => ({
			...section,
			columns: section.columns.map((column) => ({
				...column,
				fields: column.fields.map((f) => {
					const trigger = triggers[f.fieldname];
					if (!trigger) return f;
					const prev = f.ui?.on?.change;
					return {
						...f,
						ui: {
							...f.ui,
							on: {
								...f.ui?.on,
								change: prev
									? ([] as ((...a: any[]) => void)[])
											.concat(prev)
											.concat((value: any) => trigger(doc, value))
									: (value: any) => trigger(doc, value),
							},
						},
					};
				}),
			})),
		})),
	}));
}

const layout = computed<FormLayoutSchema>(() =>
	scriptEnabled.value ? withBehaviour(metaLayout.value) : metaLayout.value
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
</script>
