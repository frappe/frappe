<template>
	<!--
		Recipient entry on top of MultiSelect. MultiSelect is value-keyed
		(string emails), so the rich `{ email, label, image }` data rides as
		per-option metadata: we render avatars + display names in the dropdown
		rows and in the trigger summary, while the model stays a list of
		Recipient objects. Whatever the user types becomes a creatable option,
		but only once it's a valid email — which doubles as inline validation.
	-->
	<MultiSelect
		v-model="emails"
		variant="ghost"
		:options="options"
		:placeholder="placeholder"
		empty-text="Type an email address"
		@update:query="query = $event"
	>
		<template #item-prefix="{ item }">
			<Avatar
				size="sm"
				:image="(item.image as string) || undefined"
				:label="item.label || item.value"
			/>
		</template>

		<template #summary="{ selectedOptions, summary }">
			<span v-if="!selectedOptions.length" class="truncate text-ink-gray-4">
				{{ summary }}
			</span>
			<span v-else class="flex flex-wrap items-center gap-1">
				<span
					v-for="option in selectedOptions"
					:key="option.value"
					class="flex items-center gap-1 rounded bg-surface-gray-2 px-1.5 py-0.5 text-sm text-ink-gray-8"
				>
					<Avatar
						v-if="option.image"
						size="xs"
						:image="option.image as string"
						:label="option.label || option.value"
					/>
					{{ option.label || option.value }}
				</span>
			</span>
		</template>
	</MultiSelect>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { Avatar, MultiSelect } from "frappe-ui";
import type { MultiSelectOption } from "frappe-ui";
import type { Recipient } from "../types";

defineProps<{ placeholder?: string }>();
const model = defineModel<Recipient[]>({ default: () => [] });

const query = ref("");

// Minimal, permissive email check — good enough to gate creation without
// pulling in a validation dependency.
function isValidEmail(value: string) {
	return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

// Bridge the rich Recipient[] model to MultiSelect's string[] of emails.
// Retained recipients keep their label/image; a newly typed email becomes a
// bare `{ email }` until the host resolves it.
const emails = computed<string[]>({
	get: () => model.value.map((recipient) => recipient.email),
	set: (next) => {
		const known = new Map(model.value.map((r) => [r.email, r]));
		model.value = next.map((email) => known.get(email) ?? { email });
	},
});

const options = computed<MultiSelectOption[]>(() => {
	const selected = model.value.map((recipient) => ({
		label: recipient.label || recipient.email,
		value: recipient.email,
		image: recipient.image,
	}));
	const typed = query.value.trim();
	if (typed && isValidEmail(typed) && !emails.value.includes(typed)) {
		return [{ label: typed, value: typed }, ...selected];
	}
	return selected;
});
</script>
