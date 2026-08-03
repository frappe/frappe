<template>
	<div class="px-2.5">
		<Row v-if="showFrom" label="From" :items-center="true">
			<!-- -ml-2 cancels the ghost trigger's px-2 so text aligns with the inputs below. -->
			<Select v-model="from" :options="senderOptions" variant="ghost" class="-ml-2" />
		</Row>

		<Row v-if="showSubject" label="Subject" :items-center="true">
			<input
				v-model="subject"
				type="text"
				class="flex-1 border-0 bg-transparent p-0 text-base text-ink-gray-8 focus:ring-0"
			/>
		</Row>

		<Row v-if="showTo" label="To">
			<RecipientSelect v-model="model.to" class="flex-1" :search="search" />
			<div v-if="rows.length" class="flex shrink-0 items-center gap-1">
				<Button
					v-for="field in rows"
					:key="field"
					variant="ghost"
					:label="field.toUpperCase()"
					:class="open[field] ? '!bg-surface-gray-4' : '!text-ink-gray-5'"
					@click="toggle(field)"
					size="xs"
				/>
			</div>
		</Row>

		<template v-for="field in rows" :key="field">
			<Row v-if="open[field]" :label="field.toUpperCase()">
				<RecipientSelect v-model="model[field]" class="flex-1" :search="search" />
			</Row>
		</template>
		<div class="border-b bg-surface-gray-1 mt-1"></div>
	</div>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from "vue";
import { Button, Select } from "frappe-ui";
import RecipientSelect from "./RecipientSelect.vue";
import Row from "./HeaderRow.vue";
import type { HeaderField, Recipient, Recipients, RecipientSearch } from "../types";

const props = withDefaults(
	defineProps<{
		fields?: HeaderField[];
		senders?: Recipient[];
		search?: RecipientSearch;
	}>(),
	{ fields: () => ["to", "cc", "bcc"], senders: () => [] }
);

const model = defineModel<Recipients>({ required: true });
const subject = defineModel<string>("subject", { default: "" });
const from = defineModel<string>("from", { default: "" });

const OPTIONAL = ["cc", "bcc"] as const;
type OptionalField = "cc" | "bcc";

const showFrom = computed(() => props.fields.includes("from"));
const showSubject = computed(() => props.fields.includes("subject"));
const showTo = computed(() => props.fields.includes("to"));
const rows = computed(() => OPTIONAL.filter((field) => props.fields.includes(field)));

const senderOptions = computed(() =>
	props.senders.map((sender) => ({
		label: sender.label || sender.email,
		value: sender.email,
	}))
);

// Default to the first sender so the From row never sits unselected.
watch(
	[showFrom, () => props.senders],
	([show, senders]) => {
		if (show && !from.value && senders.length) from.value = senders[0].email;
	},
	{ immediate: true }
);

const open = reactive<Record<OptionalField, boolean>>({ cc: false, bcc: false });

// Prefilled recipients auto-open their row.
for (const field of OPTIONAL) {
	watch(
		() => model.value[field].length,
		(count) => {
			if (count) open[field] = true;
		},
		{ immediate: true }
	);
}

// Closing a row drops its recipients so none are sent invisibly.
function toggle(field: OptionalField) {
	open[field] = !open[field];
	if (!open[field]) model.value[field] = [];
}
</script>
