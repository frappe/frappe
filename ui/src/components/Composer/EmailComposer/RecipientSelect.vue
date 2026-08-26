<!-- Wrapper div so flex-1 applies: MultiEmailInput puts attrs.class on its inner box. -->
<template>
	<div class="w-full flex-1">
		<!-- min-h-6 covers the chip height so the first chip doesn't grow the row. -->
		<MultiEmailInput
			v-model="emails"
			:options="options"
			:loading="loading"
			:placeholder="placeholder"
			class="min-h-6 !gap-1 !bg-transparent !p-0"
			@update:query="onQuery"
		>
			<!-- Always show the avatar; the default hides it when imageless. -->
			<template #tag="{ value, option, removeTag }">
				<Avatar size="xs" :image="option?.image" :label="option?.label || value" />
				<!-- leading-4 fits descender ink; truncate's overflow clips tighter leadings. -->
				<span class="mb-0.5 leading-4 truncate">{{ option?.label || value }}</span>
				<button
					class="grid size-4 place-items-center rounded-sm text-ink-gray-5 hover:bg-surface-gray-4"
					@click.stop="removeTag"
				>
					<FeatherIcon name="x" class="size-3" />
				</button>
			</template>

			<!-- Put the email on its own line; the default crams it under the name. -->
			<template #option-label="{ option }">
				<div class="flex min-w-0 flex-col gap-0.5 leading-tight">
					<span class="truncate text-base text-ink-gray-8">{{ option.label }}</span>
					<span
						v-if="option.label !== option.value"
						class="truncate text-p-sm text-ink-gray-5"
					>
						{{ option.value }}
					</span>
				</div>
			</template>
		</MultiEmailInput>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { computedAsync, useDebounceFn } from "@vueuse/core";
import { Avatar, FeatherIcon, toast } from "frappe-ui";
import { MultiEmailInput, type MultiEmailOption } from "frappe-ui/experimental";
import type { Recipient, RecipientSearch } from "../types";

const props = withDefaults(defineProps<{ placeholder?: string; search?: RecipientSearch }>(), {
	placeholder: "",
});
const model = defineModel<Recipient[]>({ default: () => [] });

const loading = ref(false);

// Bridge plain emails <-> Recipient objects; Set() dedupes repeated seeds.
const emails = computed<string[]>({
	get: () => [...new Set(model.value.map((recipient) => recipient.email))],
	set: (next) => {
		const known = new Map([...searchResults.value, ...model.value].map((r) => [r.email, r]));
		model.value = next.map((email) => known.get(email) ?? { email });
	},
});

const options = computed<MultiEmailOption[]>(() =>
	searchResults.value.map((recipient) => ({
		label: recipient.label || recipient.email,
		value: recipient.email,
		image: recipient.image,
	}))
);

// null until the user searches, so the composer doesn't fetch on mount.
const query = ref<string | null>(null);
const onQuery = useDebounceFn((value: string) => (query.value = value), 250);

// computedAsync drops superseded responses, so a slow earlier request can't
// clobber newer results.
const searchResults = computedAsync<Recipient[]>(
	async () => {
		if (query.value === null || !props.search) return [];
		return props.search(query.value);
	},
	[],
	{
		evaluating: loading,
		onError: () => toast.error("Couldn't load recipients."),
	}
);
</script>

<style scoped>
/* Hide the box's focus ring for a seamless row; chips keep their aria-current ring. */
:deep([data-slot="control"]:focus-within) {
	box-shadow: none;
	outline: none;
}

/* Clear outline on chips against the transparent container. */
:deep([data-slot="tag"]) {
	@apply border-outline-gray-2;
}

/* Backspace selects the last chip (aria-current). Its own ring utilities are
   often missing (consumers rarely scan frappe-ui/experimental for Tailwind
   content), so compile the ring here. */
:deep([data-slot="tag"][aria-current="true"]) {
	@apply ring-2 ring-outline-gray-3;
}
</style>
