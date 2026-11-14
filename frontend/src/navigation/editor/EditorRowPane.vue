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
					<p v-if="refusal" class="text-xs text-ink-red-4" data-refusal>{{ refusal }}</p>
				</div>
			</div>

			<div
				class="mt-auto flex h-[49px] shrink-0 items-center border-t border-outline-gray-1"
			>
				<div class="-mx-2 flex items-center gap-1" data-row-actions>
					<Button
						variant="ghost"
						:icon-left="row.hidden ? 'lucide-eye' : 'lucide-eye-off'"
						:label="row.hidden ? __('Show') : __('Hide')"
						@click="emit('toggle')"
					/>
				</div>
			</div>
		</template>

		<p v-else class="m-auto text-sm text-ink-gray-5">{{ __("Pick a row to change it.") }}</p>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Button, FormControl, Select } from "frappe-ui";
import { __ } from "@/i18n";
import IconPicker from "@/icons/IconPicker.vue";
import { type EditorRow, isOwn, originOf, type Scope } from "./draft";
import EditorPaneHeading from "./EditorPaneHeading.vue";

const props = defineProps<{
	row: EditorRow | undefined;
	scope: Scope;
	/** Rows a row may sit under, as options; empty on the rail. */
	parents: { label: string; value: string }[];
	canPlace: boolean;
	appTitle: string;
	refusal: string | null;
	iconFor: (row: EditorRow) => string;
	titleFor: (row: EditorRow) => string;
}>();
const emit = defineEmits<{
	update: [fields: Partial<EditorRow>];
	nest: [parent: string | null];
	toggle: [];
}>();

const own = computed(() => !!props.row && isOwn(props.row.key, props.scope));
const target = computed(() => props.row?.link_to ?? props.row?.url ?? props.row?.item_type ?? "");
const originLabel = computed(() => {
	const origin = props.row ? originOf(props.row.key) : "app";
	if (origin === "user") return __("Added by you");
	if (origin === "site") return __("Added for everyone");
	return __("From {0}", [props.appTitle]);
});
</script>
