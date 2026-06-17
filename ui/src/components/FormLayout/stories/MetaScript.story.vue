<!--
  Demo of the *meta/layout scripting* seam. A base schema is produced once
  (here hand-written; in a real app from `useDoctypeLayout`), then a list of
  declarative `MetaOp`s is applied by `applyMetaScript` **before** the schema
  reaches `FormLayout`. Toggling the script re-runs the transform and the form
  re-renders live — no prop, provide, or event on `FormLayout`; the script lives
  entirely in this host layer.

  The "script" is an in-memory `MetaOp[]` for now. Server storage + a real
  syntax (a `new Function` controller) are a later layer; the seam is the point.
-->
<template>
	<div class="p-6 max-w-3xl">
		<label class="flex items-center gap-2 text-sm text-ink-gray-7 mb-4">
			<input type="checkbox" v-model="scriptEnabled" />
			Apply meta script
		</label>

		<FormLayout v-model:doc="doc" :layout="layout" />

		<div class="mt-6 text-xs text-ink-gray-6">
			<p class="font-medium mb-1">Ops applied:</p>
			<pre>{{ scriptEnabled ? ops : "(none)" }}</pre>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import FormLayout from "../FormLayout.vue";
import { applyMetaScript } from "../applyMetaScript";
import type { MetaOp } from "../applyMetaScript";
import type { FormLayoutSchema } from "../types";

const doc = reactive<Record<string, any>>({
	title: "Sample",
	status: "Open",
});

const baseLayout: FormLayoutSchema = [
	{
		name: "main",
		label: "Main",
		sections: [
			{
				name: "details",
				label: "Details",
				columns: [
					{
						name: "col",
						fields: [
							{ fieldname: "title", fieldtype: "Data", label: "Title" },
							{
								fieldname: "status",
								fieldtype: "Select",
								label: "Status",
								options: "Open\nClosed",
							},
							{
								fieldname: "internal_notes",
								fieldtype: "Text",
								label: "Internal Notes",
							},
						],
					},
				],
			},
		],
	},
];

// The in-memory "script": relabel a field, hide one, and inject a new one.
const ops: MetaOp[] = [
	{ op: "setFieldProperty", fieldname: "title", prop: "label", value: "Deal Title (scripted)" },
	{ op: "hideField", fieldname: "internal_notes" },
	{
		op: "addField",
		after: "status",
		field: {
			fieldname: "priority",
			fieldtype: "Select",
			label: "Priority",
			options: "Low\nHigh",
		},
	},
];

const scriptEnabled = ref(true);

// The transform sits between the base schema and `FormLayout` — exactly where
// `applyMetaScript` is designed to run in the real pipeline.
const layout = computed(() =>
	scriptEnabled.value ? applyMetaScript(baseLayout, ops) : baseLayout
);
</script>
