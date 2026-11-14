<!-- The right pane: the chosen row's heading, fields and actions. Edits apply as you type. -->
<template>
	<div class="flex min-h-0 flex-1 flex-col overflow-y-auto px-6 pt-5" data-editor-pane>
		<template v-if="row">
			<EditorPaneHeading :icon="iconFor(row)" :title="titleFor(row)" :origin="originLabel" />
			<p v-if="!own" class="-mt-3 mb-5 text-sm text-ink-gray-5">
				{{
					__(
						"You can rename it, change its icon, hide it or move it. Its type and target stay."
					)
				}}
			</p>

			<div class="flex flex-col gap-3">
				<FormControl
					:modelValue="target"
					:label="__('Target')"
					variant="outline"
					disabled
					class="[&_input]:text-ink-gray-7"
				/>
				<FormControl
					type="text"
					:modelValue="row.label ?? ''"
					:label="__('Label')"
					:placeholder="titleFor(row)"
					data-field="label"
					@update:modelValue="(value: string) => emit('update', { label: value })"
				/>
				<div data-field="icon">
					<IconPicker
						:modelValue="row.icon ?? ''"
						:label="__('Icon')"
						@update:modelValue="(value: string) => emit('update', { icon: value })"
					/>
				</div>
				<div v-if="canPlace" class="flex flex-col gap-1">
					<Select
						:modelValue="row.parent_key ?? ''"
						:options="parents"
						:label="__('Place under')"
						data-field="parent"
						@update:modelValue="(value: string) => emit('nest', value || null)"
					/>
					<p v-if="refusal" class="text-p-sm text-ink-red-7" role="alert" data-refusal>
						{{ refusal }}
					</p>
				</div>
			</div>
			<!-- With no Place under, a refused Move to, sidebar or delete says why above the actions. -->
			<p
				v-if="refusal && !canPlace"
				class="mt-3 text-p-sm text-ink-red-7"
				role="alert"
				data-refusal
			>
				{{ refusal }}
			</p>

			<div
				class="mt-auto flex h-[49px] shrink-0 items-center border-t border-outline-gray-1"
			>
				<div class="-mx-2 flex flex-1 items-center gap-1" data-row-actions>
					<Dropdown
						v-if="moveTargets.length"
						:options="moveOptions"
						side="bottom"
						align="start"
					>
						<Button
							variant="ghost"
							icon-left="lucide-corner-down-right"
							:label="__('Move to…')"
							data-move-to
						/>
					</Dropdown>
					<Button
						v-if="canGiveSidebar"
						variant="ghost"
						icon-left="lucide-panel-left"
						:label="__('Give it a sidebar')"
						data-give-sidebar
						@click="emit('giveSidebar')"
					/>
					<Button
						v-if="canRemoveSidebar"
						variant="ghost"
						icon-left="lucide-panel-left-close"
						:label="__('Remove its sidebar')"
						data-remove-sidebar
						@click="emit('removeSidebar')"
					/>
					<!-- An own row is deleted, not hidden: the server keeps no hidden on it. -->
					<Button
						v-if="!canDelete"
						variant="ghost"
						:icon-left="row.hidden ? 'lucide-eye' : 'lucide-eye-off'"
						:label="row.hidden ? __('Show') : __('Hide')"
						data-toggle
						@click="emit('toggle')"
					/>
					<Button
						v-if="canDelete"
						class="ml-auto"
						variant="ghost"
						theme="red"
						icon-left="lucide-trash-2"
						:label="deleteLabel"
						data-delete
						@click="emit('delete')"
					/>
				</div>
			</div>
		</template>

		<p v-else class="m-auto text-sm text-ink-gray-5">{{ __("Pick a row to change it.") }}</p>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Button, Dropdown, FormControl, Select } from "frappe-ui";
import { __ } from "@/i18n";
import IconPicker from "@/icons/IconPicker.vue";
import { type EditorRow, isOwn, originOf, RAIL, type Scope } from "./draft";
import EditorPaneHeading from "./EditorPaneHeading.vue";

const props = defineProps<{
	row: EditorRow | undefined;
	scope: Scope;
	/** Rows a row may sit under, as options; empty on the rail. */
	parents: { label: string; value: string }[];
	canPlace: boolean;
	/** The containers this row can move to, as `{label, value}`; empty when it can go nowhere. */
	moveTargets: { label: string; value: string }[];
	canGiveSidebar: boolean;
	canRemoveSidebar: boolean;
	/** The level being edited added this row: only such a row can be deleted. */
	canDelete: boolean;
	/** How many own rows Delete takes with this one, itself included. */
	deleteCount: number;
	appTitle: string;
	refusal: string | null;
	iconFor: (row: EditorRow) => string;
	titleFor: (row: EditorRow) => string;
}>();
const emit = defineEmits<{
	update: [fields: Partial<EditorRow>];
	nest: [parent: string | null];
	toggle: [];
	delete: [];
	moveTo: [container: string];
	giveSidebar: [];
	removeSidebar: [];
}>();

// The rail first, then the sidebars under their own heading, so "Rail" never reads as a sidebar's name.
const moveOptions = computed(() => {
	const option = (target: { label: string; value: string }) => ({
		label: target.label,
		onClick: () => emit("moveTo", target.value),
	});
	const sidebars = props.moveTargets.filter((target) => target.value !== RAIL).map(option);
	return [
		...props.moveTargets.filter((target) => target.value === RAIL).map(option),
		...(sidebars.length ? [{ group: __("Sidebars"), items: sidebars }] : []),
	];
});
const deleteLabel = computed(() =>
	props.deleteCount > 2
		? __("Delete with {0} rows", [props.deleteCount - 1])
		: props.deleteCount === 2
		? __("Delete with 1 row")
		: __("Delete")
);

const own = computed(() => !!props.row && isOwn(props.row.key, props.scope));
const target = computed(() => props.row?.link_to ?? props.row?.url ?? props.row?.item_type ?? "");
const originLabel = computed(() => {
	const origin = props.row ? originOf(props.row.key) : "app";
	if (origin === "user") return __("Added by you");
	if (origin === "site") return __("Added for everyone");
	return __("From {0}", [props.appTitle]);
});
</script>
