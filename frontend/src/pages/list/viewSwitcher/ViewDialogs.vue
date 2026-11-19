<!-- A view menu's question: a name or a confirmation, one solid button; a failed run stays open. -->
<template>
	<Dialog v-model="open" :title="title" size="sm" :actions="actions" @close="emit('close')">
		<template #default>
			<div v-if="asksName" class="flex flex-col gap-2">
				<FormControl
					v-model="label"
					type="text"
					:label="__('Name')"
					autofocus
					@focus="selectAll"
					@keydown.enter="confirm"
				/>
				<p class="text-sm text-ink-gray-6">{{ hint }}</p>
			</div>
			<p v-else class="text-base text-ink-gray-6">{{ hint }}</p>
			<p v-if="failure" class="mt-2 whitespace-pre-line text-sm text-ink-red-4">
				{{ failure }}
			</p>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { Dialog, FormControl } from "frappe-ui";
import { computed, ref } from "vue";
import { __ } from "@/i18n";
import { errorMessage } from "@/recordPage/errorMessage";
import { useReadableDialog } from "@/shell/dialogs/readableDialogs";
import type { ViewRequest, ViewRequestKind } from "./viewMenu";

const props = defineProps<{
	request: ViewRequest;
	/** Runs the list act by its short name; rejects with the reason it was refused. */
	run: (act: string, value?: unknown) => Promise<unknown>;
}>();
const emit = defineEmits<{ close: [] }>();

const { kind, view } = props.request;
const name = view?.label ?? "";
const open = ref(true);
const working = ref(false);
const failure = ref("");
const label = ref(kind === "save_as_new" ? __("{0} copy", [name]) : name);

const asksName = kind === "rename" || kind === "save_as_new";

const WORDS: Record<ViewRequestKind, { title: string; hint: string; button: string }> = {
	rename: {
		title: __("Rename view"),
		hint: __("Only the name changes. Links, stars and sidebar rows keep working."),
		button: __("Rename"),
	},
	save_as_new: {
		title: __("Save as new view"),
		hint: __("Saved to My views with the current filters and sort."),
		button: __("Save"),
	},
	delete: {
		title: __("Delete “{0}”?", [name]),
		hint: __("Sidebar rows that open it show “View deleted”."),
		button: __("Delete"),
	},
	restore: {
		title: __("Restore the app's “{0}”?", [name]),
		hint: __("The site's copy goes, and everyone sees the app's view again."),
		button: __("Restore"),
	},
	publish: {
		title: __("Publish “{0}”?", [name]),
		hint: __(
			"Everyone on the site sees it under Site views. Only a site administrator can change it then."
		),
		button: __("Publish"),
	},
};
const { title, hint, button } = WORDS[kind];

const RUNS: Record<ViewRequestKind, () => [string, unknown]> = {
	rename: () => ["rename_view", { key: view!.key, label: label.value.trim() }],
	save_as_new: () => ["save_view_as", { label: label.value.trim() }],
	delete: () => ["delete_view", { key: view!.key }],
	restore: () => ["delete_view", { key: view!.key }],
	publish: () => ["publish_view", { key: view!.key }],
};

const actions = computed(() => [
	{
		label: button,
		variant: "solid" as const,
		theme: kind === "delete" ? ("red" as const) : ("gray" as const),
		loading: working.value,
		disabled: asksName && !label.value.trim(),
		"data-act": `list.${RUNS[kind]()[0]}`,
		onClick: confirm,
	},
]);

async function confirm() {
	if (working.value || (asksName && !label.value.trim())) return;
	working.value = true;
	failure.value = "";
	try {
		await props.run(...RUNS[kind]());
		open.value = false;
	} catch (error) {
		failure.value = errorMessage(error);
	} finally {
		working.value = false;
	}
}

// Typing over the suggested name needs no select first.
const selectAll = (event: FocusEvent) => (event.target as HTMLInputElement).select?.();

useReadableDialog(open, () => ({
	kind: kind === "delete" ? "danger" : asksName ? "dialog" : "confirm",
	title,
	message: hint,
	buttons: [button],
}));
</script>
