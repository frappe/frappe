<template>
	<!-- Adapter over frappe-ui's MultiEmailInput: bridges Recipient objects
		 (name + avatar) to the plain email strings it models. -->
	<!-- Wrapper so the row's flex-1 lands on a flex child: MultiEmailInput puts
		 attrs.class on its inner box, not its root. -->
	<div class="w-full flex-1">
		<MultiEmailInput
			v-model="emails"
			:options="options"
			:loading="loading"
			:placeholder="placeholder"
			class="!gap-1 !bg-transparent !p-0"
			@update:query="onQuery"
		>
			<!-- Always show the avatar; the default hides it when imageless. -->
			<template #tag="{ value, option, removeTag }">
				<Avatar size="xs" :image="option?.image" :label="option?.label || value" />
				<span class="truncate">{{ option?.label || value }}</span>
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
import { useDebounceFn } from "@vueuse/core";
import { Avatar, FeatherIcon } from "frappe-ui";
import { MultiEmailInput, type MultiEmailOption } from "frappe-ui/experimental";
import type { Recipient, RecipientSearch } from "../types";

const props = withDefaults(defineProps<{ placeholder?: string; search?: RecipientSearch }>(), {
	placeholder: "",
});
const model = defineModel<Recipient[]>({ default: () => [] });

const loading = ref(false);
const searchResults = ref<Recipient[]>([]);

// Bridge plain emails <-> Recipient objects, restoring each chip's name/avatar
// from its match or existing entry. Set() dedupes so a repeated seed can't
// collide on key.
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

// Drop stale responses so a slow earlier request can't clobber newer results.
let requestId = 0;
async function runSearch(query: string) {
	if (!props.search) return;
	const id = ++requestId;
	loading.value = true;
	try {
		const results = await props.search(query);
		if (id === requestId) searchResults.value = results;
	} finally {
		if (id === requestId) loading.value = false;
	}
}

const onQuery = useDebounceFn(runSearch, 250);
</script>

<style scoped>
/* Hide the box's focus ring for a seamless row; chips keep their aria-current ring. */
:deep([data-slot="control"]:focus-within) {
	box-shadow: none;
	outline: none;
}

/* Clear outline on chips against the transparent container. */
:deep([data-slot="tag"]) {
	border-color: var(--outline-gray-2);
}
</style>
