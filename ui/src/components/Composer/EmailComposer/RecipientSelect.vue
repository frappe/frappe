<!-- Wrapper div so flex-1 applies: MultiEmailInput puts attrs.class on its inner box. -->
<template>
	<div
		ref="row"
		tabindex="-1"
		class="w-full flex-1 outline-none"
		:class="{ 'drop-target': isDragOver }"
		@dragover.prevent="isDragOver = true"
		@dragleave="onDragLeave"
		@drop.prevent="onDrop"
	>
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
				<span
					class="-my-0.5 -ml-1.5 flex min-w-0 items-center gap-1 py-0.5 pl-1.5"
					draggable="true"
					@dragstart="onDragStart($event, value, option)"
				>
					<Avatar size="xs" :image="option?.image" :label="option?.label || value" />
					<span class="mb-0.5 leading-4 truncate">{{ option?.label || value }}</span>
				</span>
				<button
					class="grid size-4 place-items-center rounded-1 text-ink-gray-5 hover:bg-surface-gray-4"
					@click.stop="removeTag"
				>
					<LucideX class="size-3" />
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
import { computed, ref, useTemplateRef } from "vue";
import { computedAsync, useDebounceFn } from "@vueuse/core";
import { Avatar, toast } from "frappe-ui";
import LucideX from "~icons/lucide/x";
import { MultiEmailInput, type MultiEmailOption } from "frappe-ui/experimental";
import type { Recipient, RecipientSearch } from "../types";

const props = withDefaults(defineProps<{ placeholder?: string; search?: RecipientSearch }>(), {
	placeholder: "",
});
const model = defineModel<Recipient[]>({ default: () => [] });

const loading = ref(false);

const emit = defineEmits<{ showCcBcc: []; move: [recipient: Recipient] }>();

// same payload key frappe mail uses, so the two stay swappable
const DRAG_TYPE = "recipient";
const isDragOver = ref(false);
const row = useTemplateRef<HTMLElement>("row");

function onDragStart(event: DragEvent, email: string, option?: MultiEmailOption) {
	emit("showCcBcc");
	// the open suggestion list covers the rows being dragged to, and it only
	// closes when focus leaves the input
	row.value?.focus();
	if (!event.dataTransfer) return;
	event.dataTransfer.effectAllowed = "move";
	event.dataTransfer.setData(
		DRAG_TYPE,
		JSON.stringify({ email, label: option?.label, image: option?.image })
	);
	// float the chip itself, not just the part carrying the draggable attribute
	const chip = (event.currentTarget as HTMLElement).closest<HTMLElement>('[data-slot="tag"]');
	if (!chip) return;
	const box = chip.getBoundingClientRect();
	const floater = floatingCopyOf(chip, box);
	event.dataTransfer.setDragImage(floater, event.clientX - box.left, event.clientY - box.top);
	requestAnimationFrame(() => floater.remove());
}

// the composer blurs its backdrop, and a chip snapshotted inside that comes out
// with white corners, so drag a copy parked on the body instead
function floatingCopyOf(chip: HTMLElement, box: DOMRect) {
	const copy = chip.cloneNode(true) as HTMLElement;
	copy.style.position = "fixed";
	copy.style.top = "-1000px";
	copy.style.left = "-1000px";
	copy.style.width = `${box.width}px`;
	copy.style.height = `${box.height}px`;
	copy.style.pointerEvents = "none";
	document.body.appendChild(copy);
	return copy;
}

// dragleave also fires moving between children, ignore those
function onDragLeave(event: DragEvent) {
	const leaving = event.relatedTarget as Node | null;
	if (!leaving || !(event.currentTarget as HTMLElement).contains(leaving)) {
		isDragOver.value = false;
	}
}

function onDrop(event: DragEvent) {
	isDragOver.value = false;
	const data = event.dataTransfer?.getData(DRAG_TYPE);
	if (!data) return;
	emit("move", JSON.parse(data) as Recipient);
}

// Bridge plain emails <-> Recipient objects; Set() dedupes repeated seeds.
const emails = computed<string[]>({
	get: () => [...new Set(model.value.map((recipient) => recipient.email))],
	set: (next) => {
		const known = new Map([...searchResults.value, ...model.value].map((r) => [r.email, r]));
		model.value = next.map((email) => known.get(email) ?? { email });
	},
});

// Model recipients go in too: MultiEmailInput learns a chip's details from
// options, so one seeded with a label is known before any search runs.
const options = computed<MultiEmailOption[]>(() => {
	const byEmail = new Map<string, Recipient>();
	for (const recipient of [...searchResults.value, ...model.value]) {
		if (!byEmail.has(recipient.email)) byEmail.set(recipient.email, recipient);
	}
	return [...byEmail.values()].map((recipient) => ({
		label: recipient.label || recipient.email,
		value: recipient.email,
		image: recipient.image,
	}));
});

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
/* the row a chip can be dropped on */
.drop-target {
	@apply rounded-4 ring-2 ring-outline-gray-3;
}

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
