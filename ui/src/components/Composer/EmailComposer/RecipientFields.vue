<template>
	<!-- Subject and To are shown when enabled by `fields`; Cc/Bcc are revealed by
		 the toggles on the To row (or whenever they already carry recipients). -->
	<div class="px-2.5">
		<Row
			v-if="showSubject || subject"
			label="Subject"
			label-class="w-[52px]"
			:items-center="true"
		>
			<input
				v-model="subject"
				type="text"
				class="flex-1 border-0 bg-transparent p-0 text-base text-ink-gray-8 focus:ring-0"
			/>
		</Row>

		<Row label="To">
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
import { Button } from "frappe-ui";
import RecipientSelect from "./RecipientSelect.vue";
import Row from "./RecipientRow.vue";
import type { Field, Recipients, RecipientSearch } from "../types";

const props = withDefaults(
	defineProps<{
		/** Rows offered beyond the always-present "To". */
		fields?: Field[];
		search?: RecipientSearch;
	}>(),
	{ fields: () => ["cc", "bcc"] }
);

const model = defineModel<Recipients>({ required: true });
const subject = defineModel<string>("subject", { default: "" });

// The optional recipient rows, in fixed order. `subject` is handled separately
// (it's a plain text field, not a recipient list).
const OPTIONAL = ["cc", "bcc"] as const;
type OptionalField = typeof OPTIONAL[number];

const showSubject = computed(() => props.fields.includes("subject"));
// Which optional rows this composer offers — each gets a toggle button + a row.
const rows = computed(() => OPTIONAL.filter((field) => props.fields.includes(field)));

// Whether each optional row is open — the single source of truth for both the
// row and its toggle button, so the button's highlighted state always matches
// what's on screen.
const open = reactive<Record<OptionalField, boolean>>({ cc: false, bcc: false });

// Auto-open a row as soon as it carries recipients — prefilled at mount, or
// seeded later by the host (e.g. a reply that pre-fills Cc). Without this a
// pre-filled row would show under an "off"-looking toggle, and clicking it
// would silently wipe those recipients.
for (const field of OPTIONAL) {
	watch(
		() => model.value[field].length,
		(count) => {
			if (count) open[field] = true;
		},
		{ immediate: true }
	);
}

// Closing a row drops its recipients — hidden recipients would otherwise be
// sent invisibly. Because the toggle honestly reflects the open state, this is
// a deliberate action, not a silent surprise.
function toggle(field: OptionalField) {
	open[field] = !open[field];
	if (!open[field]) model.value[field] = [];
}
</script>
