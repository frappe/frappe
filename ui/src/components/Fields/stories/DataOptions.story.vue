<!-- A Data field per option, editable, read-only and empty, with its stored and committed value. -->
<template>
	<div class="flex max-w-3xl flex-col gap-8 p-6">
		<div v-for="option in OPTIONS" :key="option" class="grid grid-cols-3 gap-4">
			<div v-for="state in STATES" :key="state" class="flex flex-col gap-2">
				<component
					:is="state === 'read-only' ? ReadOnlyField : TextField"
					v-model="doc[key(option, state)]"
					:field="field(option, state)"
					@change="committed[key(option, state)] = $event"
				/>
				<pre
					v-if="state !== 'read-only'"
					class="whitespace-pre-wrap text-xs text-ink-gray-6"
				>
stored = {{ JSON.stringify(doc[key(option, state)]) }}
committed = {{ JSON.stringify(committed[key(option, state)] ?? null) }}</pre
				>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { provide, reactive, ref } from "vue";
import TextField from "../TextField.vue";
import ReadOnlyField from "../ReadOnlyField.vue";
import { DocKey } from "../types";
import type { FieldMeta } from "../types";

const OPTIONS = ["Email", "URL", "Phone", "Name", "IBAN", "Barcode"] as const;
const STATES = ["editable", "read-only", "empty"] as const;

const VALUES: Record<typeof OPTIONS[number], string> = {
	Email: "ada@example.com, grace@example.com",
	URL: "https://frappe.io",
	Phone: "+91 99999 99999",
	Name: "Ada Lovelace",
	IBAN: "DE89370400440532013000",
	Barcode: "4006381333931",
};

const doc = ref<Record<string, any>>(
	Object.fromEntries(
		OPTIONS.flatMap((option) =>
			STATES.map((state) => [key(option, state), state === "empty" ? "" : VALUES[option]])
		)
	)
);
const committed = reactive<Record<string, unknown>>({});

provide(DocKey, doc);

function key(option: string, state: string): string {
	return `${option}_${state}`.toLowerCase().replace("-", "_");
}

function field(option: string, state: typeof STATES[number]): FieldMeta {
	return {
		fieldname: key(option, state),
		fieldtype: "Data",
		options: option,
		label: `${option}, ${state}`,
		readOnly: state === "read-only",
	};
}
</script>
