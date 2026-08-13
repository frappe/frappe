<template>
	<div class="flex min-h-0 gap-4">
		<!-- The list is the precedence explanation: creation order is run order, so
		     the numbers are not decoration — they say who wins. -->
		<div class="flex w-56 shrink-0 flex-col">
			<div class="flex items-center justify-between gap-2">
				<span class="text-p-sm-medium text-ink-gray-7">Run order</span>
				<Button
					iconLeft="lucide-plus"
					size="sm"
					label="New"
					:disabled="loading"
					@click="naming = true"
				/>
			</div>
			<p class="mt-1 text-p-xs text-ink-gray-5">
				Scripts run top to bottom. The last one to run wins.
			</p>

			<!-- FP1 fallback: frappe-ui has no single-select list primitive (ListItem
			     is a title/subtitle row, Tabs is horizontal), so the roles and the
			     arrow-key handling below are hand-rolled deliberately. -->
			<div
				class="mt-3 flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto"
				role="listbox"
				aria-label="Page scripts"
				@keydown.down.prevent="step(1)"
				@keydown.up.prevent="step(-1)"
			>
				<Skeleton v-if="loading" class="h-8 w-full" />
				<p v-else-if="!scripts.length" class="text-p-sm text-ink-gray-5">
					No page scripts for {{ dt }} yet.
				</p>
				<button
					v-for="(row, index) in scripts"
					:key="row.name"
					type="button"
					role="option"
					:aria-selected="row.name === selectedName"
					class="flex items-center gap-2 rounded px-2 py-1.5 text-left"
					:class="
						row.name === selectedName
							? 'bg-surface-gray-3 text-ink-gray-9'
							: 'text-ink-gray-7 hover:bg-surface-gray-2'
					"
					@click="select(row.name)"
				>
					<span class="w-4 shrink-0 text-p-xs text-ink-gray-4">{{ index + 1 }}</span>
					<span class="truncate text-p-sm" :class="{ 'text-ink-gray-4': !row.enabled }">
						{{ row.name }}
					</span>
					<span class="ml-auto flex shrink-0 items-center gap-1">
						<Tooltip v-if="isDirty(row)" text="Unsaved changes">
							<span class="size-1.5 rounded-full bg-surface-amber-5" />
						</Tooltip>
						<Badge v-if="!row.enabled" theme="gray" size="sm" label="Off" />
					</span>
				</button>
			</div>
		</div>

		<div class="flex min-w-0 flex-1 flex-col gap-3">
			<template v-if="selected">
				<CodeEditor
					v-model="draft"
					language="javascript"
					:style="{ '--cm-max-height': editorHeight }"
					placeholder="export default { refresh(page) {} }"
				/>
				<p class="text-p-xs text-ink-gray-5">
					An ES module whose default export is an object of event handlers. It may import
					vue, vue-router, frappe-ui and @framework/ui; nothing else resolves.
				</p>
				<p class="text-p-xs text-ink-gray-5">
					Anything a script hides is hidden from the eye, not from the server. A user who
					can't see the button can still make the call.
				</p>
				<ErrorMessage :message="error" />
				<div class="flex items-center gap-3">
					<Switch
						:modelValue="Boolean(selected.enabled)"
						size="sm"
						label="Enabled"
						:disabled="saving"
						@update:modelValue="setEnabled(selected!, $event)"
					/>
					<Button
						class="ml-auto"
						theme="red"
						label="Delete"
						:disabled="saving"
						@click="confirmingDelete = true"
					/>
					<Button
						variant="solid"
						label="Save"
						:loading="saving"
						:disabled="!dirty"
						@click="save"
					/>
				</div>
			</template>
			<div v-else class="flex flex-1 items-center justify-center">
				<ErrorMessage v-if="error" :message="error" />
				<p v-else class="text-p-sm text-ink-gray-5">Select a script, or create one.</p>
			</div>
		</div>

		<NewPageScriptDialog
			v-model="naming"
			:taken="scripts.map((row) => row.name)"
			:onSubmit="create"
		/>
		<Dialog v-model="confirmingDelete" :options="deleteOptions" />
	</div>
</template>

<script setup lang="ts">
// The generic Page Script editor: one doctype's scripts, listed in run order,
// with the selected one open in a code editor. Saving is all it does to the
// running page — the doctype publishes its change event and any mounted Record
// page replays the tier on its own.
import { computed, ref } from "vue";
import { Badge, Button, Dialog, ErrorMessage, Skeleton, Switch, Tooltip } from "frappe-ui";
import { CodeEditor } from "frappe-ui/code-editor";
import NewPageScriptDialog from "./NewPageScriptDialog.vue";
import { usePageScriptEditor } from "./usePageScriptEditor";

const props = withDefaults(
	defineProps<{
		/** The doctype whose Record page scripts these are. */
		dt: string;
		/** Cap for the code editor, as a CSS length. */
		editorHeight?: string;
	}>(),
	{ editorHeight: "24rem" },
);

const {
	scripts,
	selected,
	selectedName,
	draft,
	dirty,
	isDirty,
	loading,
	saving,
	error,
	select,
	create,
	save,
	setEnabled,
	remove,
} = usePageScriptEditor(() => props.dt);

const naming = ref(false);
const confirmingDelete = ref(false);

const deleteOptions = computed(() => ({
	title: `Delete ${selectedName.value}?`,
	message: "The script stops running everywhere. This cannot be undone.",
	actions: [
		{
			label: "Delete",
			theme: "red",
			variant: "solid",
			// The dialog closes either way: a failure is reported on the pane
			// behind it, which this would otherwise cover.
			onClick: async () => {
				try {
					if (selected.value) await remove(selected.value);
				} finally {
					confirmingDelete.value = false;
				}
			},
		},
	],
}));

function step(delta: number) {
	if (!scripts.value.length) return;
	const current = scripts.value.findIndex((row) => row.name === selectedName.value);
	const next = Math.min(Math.max(current + delta, 0), scripts.value.length - 1);
	select(scripts.value[next].name);
}
</script>
