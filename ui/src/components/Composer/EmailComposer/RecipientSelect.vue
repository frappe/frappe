<template>
	<!--
		Recipient entry for one row (To / Cc / Bcc). A thin adapter over frappe-ui's
		experimental MultiEmailInput: that component owns the chips, dropdown, paste
		and validation, while this wrapper bridges the two data shapes — the composer
		models Recipient objects (name + avatar), MultiEmailInput models plain email
		strings — and drives the host's async `search` from the input query.
	-->
	<!-- A wrapper so the row's `flex-1` lands on the flex child (the parent
		 passes it to us). MultiEmailInput puts attrs.class on its inner box, not
		 its root, so without this the field never fills the row. -->
	<div class="w-full">
		<MultiEmailInput
			v-model="emails"
			:options="options"
			:loading="loading"
			:placeholder="placeholder"
			class="!gap-1 !bg-transparent !p-0"
			@update:query="onQuery"
		>
			<!-- Match the composer's original chip: always show the avatar (the
				 default hides it without an image) with the name beside it. -->
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

			<!-- The default stacks name and email with no gap, so they read as one
				 cramped block; give the email its own line with a little breathing room. -->
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

// Default to no placeholder — the row already has its "To"/"Cc"/"Bcc" label, so
// the field should read as a seamless empty space.
const props = withDefaults(defineProps<{ placeholder?: string; search?: RecipientSearch }>(), {
	placeholder: "",
});
const model = defineModel<Recipient[]>({ default: () => [] });

const loading = ref(false);
const searchResults = ref<Recipient[]>([]);

// MultiEmailInput speaks plain email strings; the composer speaks Recipient
// objects. Bridge the two: rebuild the model from the emails MultiEmailInput
// reports, keeping each chip's name/avatar from its matched suggestion (or its
// existing entry). A typed/pasted address with no match rides as a bare email.
// De-dupe the chip list so a repeated seeded address can't collide on key.
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

// Drop stale responses so an earlier-but-slower request can't overwrite the
// latest results.
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
/* Suppress the box's focus ring (box-shadow) on focus-within — the composer
   wants the row seamless. The chips keep their own focus outline (the component
   rings the current chip via aria-current). `:deep` + the data attribute beats
   the utility's cascade. */
:deep([data-slot="control"]:focus-within) {
	box-shadow: none;
	outline: none;
}

/* Keep a clear outline on the chips so they stay distinct against the now
   transparent container (the wrapper's faint default border washes out). */
:deep([data-slot="tag"]) {
	border-color: var(--outline-gray-2);
}
</style>
