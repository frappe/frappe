<!-- The bar that takes the column labels' place while rows are selected: the count, the actions, and a clear button. -->
<template>
	<div
		class="flex h-7 w-full items-center gap-2 text-base"
		role="toolbar"
		:aria-label="__('Bulk actions')"
	>
		<span class="whitespace-nowrap text-ink-gray-9" aria-live="polite">{{ countText }}</span>
		<Button
			v-if="scope.canSelectAll.value"
			variant="ghost"
			:label="__('Select all {0}', [scope.totalText.value])"
			@click="scope.selectAll()"
		/>
		<template v-if="overCap">
			<span
				class="flex items-center gap-1 whitespace-nowrap text-sm text-ink-gray-5"
				role="status"
			>
				<Icon name="lucide-circle-alert" class="size-3.5" />
				{{ __("Over the {0} cap", [cap]) }}
			</span>
		</template>
		<template v-if="shown">
			<div class="h-4 border-s border-outline-gray-2" />
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
				<div
					v-if="layout.transitions.length"
					class="mx-1 h-4 border-s border-outline-gray-2"
				/>
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
		<!-- Tooltip drops the class it is given, so this pushes the clear button to the end. -->
		<div class="ms-auto flex shrink-0">
			<Tooltip>
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
	</div>
	<BulkStatusDialog
		v-if="dialogOpened"
		v-model="confirming"
		:doctype="doctype"
		:action="status.asked.value"
		:finished="status.finished"
		:select="status.select"
	/>
</template>

<script setup lang="ts">
import { Button, Dropdown, Icon, KeyboardShortcut, Tooltip, toast } from "frappe-ui";
import { computed, defineAsyncComponent, ref, watch } from "vue";
import { __ } from "@/i18n";
import type { BulkScope } from "@/list/useBulkScope";
import type { BulkLayout } from "./bulkLayout";
import type { BulkStatus } from "./bulkStatus";

const props = defineProps<{
	scope: BulkScope;
	doctype: string;
	cap: number;
	layout: BulkLayout;
	locked: boolean;
	status: BulkStatus;
}>();
const menuOpen = defineModel<boolean>("menuOpen", { default: false });
defineEmits<{ clear: [] }>();

const countText = computed(() =>
	props.scope.all.value
		? __("All {0} selected", [props.scope.totalText.value])
		: __("{0} selected", [props.scope.count.value])
);
const BulkStatusDialog = defineAsyncComponent({
	loader: () => import("./BulkStatusDialog.vue"),
	onError: (_error, _retry, fail) => {
		dialogOpened.value = false;
		toast.error(__("The dialog did not load. Reload the page and try again."));
		fail();
	},
});
const dialogOpened = ref(false);
const confirming = ref(false);
watch(props.status.asked, (action) => {
	if (!action) return;
	dialogOpened.value = true;
	confirming.value = true;
});

const overCap = computed(() => !props.locked && props.scope.count.value > props.cap);
const shown = computed(
	() =>
		props.layout.transitions.length ||
		props.layout.buttons.length ||
		props.layout.menu.length ||
		props.layout.trash
);
</script>
