<!-- The bar that takes the controls row's place while rows are selected: the count, the actions, and a clear button. -->
<template>
	<div
		class="flex h-7 w-full items-center gap-2 text-base"
		role="toolbar"
		:aria-label="__('Bulk actions')"
	>
		<div class="flex items-center gap-2 ps-px">
			<Checkbox :modelValue="true" :disabled="true" aria-hidden="true" />
			<span class="whitespace-nowrap text-ink-gray-9">{{
				__("{0} selected", [count])
			}}</span>
		</div>
		<template v-if="overCap">
			<span class="flex items-center gap-1 whitespace-nowrap text-sm text-ink-gray-5">
				<Icon name="lucide-circle-alert" class="size-3.5" />
				{{ __("Over the {0} cap", [cap]) }}
			</span>
		</template>
		<template v-if="shown">
			<div class="h-4 w-px bg-outline-gray-2" />
			<div class="flex items-center gap-1">
				<Button
					v-for="entry in layout.transitions"
					:key="entry.name"
					variant="subtle"
					:label="entry.label"
					:icon-left="entry.icon"
					:disabled="entry.disabled"
					@click="entry.onClick"
				/>
				<div v-if="layout.transitions.length" class="mx-1 h-4 w-px bg-outline-gray-2" />
				<Button
					v-for="entry in layout.buttons"
					:key="entry.name"
					variant="ghost"
					:label="entry.label"
					:icon-left="entry.icon"
					:disabled="entry.disabled"
					@click="entry.onClick"
				/>
				<Dropdown
					v-if="layout.menu.length"
					v-model:open="menuOpen"
					:options="layout.menu"
					side="bottom"
					align="start"
				>
					<!-- The Dropdown trigger needs a plain element: Tooltip drops the trigger's props. -->
					<div class="flex shrink-0">
						<Tooltip>
							<template v-if="!menuOpen" #content>
								<span
									class="flex items-center gap-2 [&_[data-slot=key]]:text-ink-gray-4"
								>
									{{ __("More actions") }} <KeyboardShortcut combo="Period" />
								</span>
							</template>
							<Button
								variant="ghost"
								:label="__('More')"
								icon-right="lucide-chevron-down"
							/>
						</Tooltip>
					</div>
				</Dropdown>
				<Tooltip v-if="layout.trash" :text="layout.trash.label">
					<Button
						variant="ghost"
						theme="red"
						:icon="layout.trash.icon"
						:label="layout.trash.label"
						:disabled="layout.trash.disabled"
						@click="layout.trash.onClick"
					/>
				</Tooltip>
			</div>
		</template>
		<Tooltip class="ms-auto">
			<template #content>
				<span class="flex items-center gap-2 [&_[data-slot=key]]:text-ink-gray-4">
					{{ __("Clear selection") }} <KeyboardShortcut combo="Escape" />
				</span>
			</template>
			<Button
				variant="ghost"
				icon="lucide-x"
				:label="__('Clear selection')"
				@click="$emit('clear')"
			/>
		</Tooltip>
	</div>
</template>

<script setup lang="ts">
import { Button, Checkbox, Dropdown, Icon, KeyboardShortcut, Tooltip } from "frappe-ui";
import { computed } from "vue";
import { __ } from "@/i18n";
import type { BulkLayout } from "./bulkLayout";

const props = defineProps<{ count: number; cap: number; layout: BulkLayout; locked: boolean }>();
const menuOpen = defineModel<boolean>("menuOpen", { default: false });
defineEmits<{ clear: [] }>();

const overCap = computed(() => !props.locked && props.count > props.cap);
const shown = computed(
	() =>
		props.layout.transitions.length ||
		props.layout.buttons.length ||
		props.layout.menu.length ||
		props.layout.trash
);
</script>
