<template>
	<div class="flex w-64 shrink-0 flex-col border-r border-outline-gray-1 p-3">
		<!-- The rail is labelled, not explained (ticket 23): four words and an
		     arrow replace two lines of prose, and only once there is an order to
		     describe — a list of one runs in no particular order. -->
		<div v-if="scripts.length > 1" class="flex items-center gap-1 px-1 pb-2">
			<span class="text-p-xs text-ink-gray-5">Runs in this order</span>
			<span class="text-p-xs text-ink-gray-4">↓</span>
		</div>

		<!-- Dragging is the only way to change run order, so it is gated on there
		     being an order to change: with one script the grip is absent and the
		     list is inert (ticket 23's rule that order appears only once it
		     exists). `handle` keeps the whole row clickable — only the grip
		     starts a drag, so a click still selects. -->
		<Draggable
			class="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto"
			tag="div"
			:modelValue="scripts"
			:itemKey="(row: PageScriptDoc) => row.name"
			:disabled="!reorderable"
			handle=".page-script-drag-handle"
			@update:modelValue="dropped"
		>
			<template #item="{ element: row, index }">
				<ItemListRow
					as="button"
					type="button"
					:selected="row.name === selectedName"
					:aria-current="row.name === selectedName"
					class="group cursor-pointer text-left"
					@click="emit('select', row.name)"
				>
					<template #prefix>
						<span
							v-if="reorderable"
							class="page-script-drag-handle lucide-grip-vertical size-3 shrink-0 cursor-grab text-ink-gray-3 transition-colors group-hover:text-ink-gray-5"
							aria-hidden="true"
						/>
						<span class="w-3 shrink-0 text-p-xs tabular-nums text-ink-gray-4">
							{{ index + 1 }}
						</span>
					</template>
					<template #label>
						<span
							class="block min-w-0 truncate text-p-sm"
							:class="row.enabled ? 'text-ink-gray-8' : 'text-ink-gray-4'"
						>
							{{ row.name }}
						</span>
					</template>
					<!-- Selection, unsaved-ness and enabled-ness are three separate
					     states of a row, so each gets its own mark rather than sharing
					     the row's colour. -->
					<template #suffix>
						<Tooltip v-if="isDirty(row)" text="Unsaved changes">
							<span class="size-1.5 shrink-0 rounded-full bg-surface-amber-5" />
						</Tooltip>
						<Badge v-if="!row.enabled" theme="gray" size="sm" label="Off" />
						<!-- The name says which script's menu this opens, and it is
						     the only route to Disable, Duplicate and Delete. `icon` +
						     `label` is what names an icon-only Button (ticket 35). -->
						<Dropdown :options="options(row)" align="end">
							<Button
								variant="ghost"
								size="sm"
								icon="lucide-ellipsis"
								:label="`Actions for ${row.name}`"
								class="shrink-0"
								:class="
									row.name === selectedName
										? ''
										: 'opacity-0 group-hover:opacity-100'
								"
							/>
						</Dropdown>
					</template>
				</ItemListRow>
			</template>
		</Draggable>

		<Button
			class="mt-2"
			iconLeft="lucide-plus"
			label="New script"
			:disabled="busy"
			@click="emit('create')"
		/>
	</div>
</template>

<script setup lang="ts">
// The script list: selection, run position, and every per-script action. The
// destructive ones live here rather than beside Save, so nothing routine sits
// next to them (ticket 23).
import { computed } from "vue";
import { Badge, Button, Dropdown, ItemListRow, Tooltip } from "frappe-ui";
// @ts-ignore — vuedraggable ships no bundled types
import Draggable from "vuedraggable";
import type { PageScriptDoc } from "./pageScriptApi";

const props = defineProps<{
	scripts: PageScriptDoc[];
	selectedName: string | null;
	/** Whether a row carries an unsaved edit — the row marks these. */
	isDirty: (row: PageScriptDoc) => boolean;
	/** A write is in flight; the list stays readable but adds nothing new. */
	busy?: boolean;
}>();

const emit = defineEmits<{
	select: [name: string];
	create: [];
	toggleEnabled: [row: PageScriptDoc];
	duplicate: [row: PageScriptDoc];
	remove: [row: PageScriptDoc];
	/** The whole list in its new order — order belongs to the list, not a row. */
	reorder: [names: string[]];
}>();

const reorderable = computed(() => props.scripts.length > 1);

// The rail owns no state, so it reports the dropped order rather than applying
// it: the pane holds the list, and it is the pane's write that has to be able
// to put it back if the server refuses.
function dropped(rows: PageScriptDoc[]) {
	emit(
		"reorder",
		rows.map((row) => row.name),
	);
}

function options(row: PageScriptDoc) {
	return [
		{
			label: row.enabled ? "Disable" : "Enable",
			icon: row.enabled ? "lucide-circle-slash" : "lucide-circle-check",
			onClick: () => emit("toggleEnabled", row),
		},
		{
			label: "Duplicate",
			icon: "lucide-copy",
			onClick: () => emit("duplicate", row),
		},
		{
			label: "Delete…",
			icon: "lucide-trash-2",
			theme: "red",
			onClick: () => emit("remove", row),
		},
	].map((option) => ({ ...option, disabled: props.busy }));
}
</script>
