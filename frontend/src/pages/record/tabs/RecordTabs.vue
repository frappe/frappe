<!-- The record's tab strip over one tab body. A body stays mounted, hidden, after its first
     visit, and scrolls on its own, so scroll and focus survive a switch on every tab. -->
<template>
	<div class="flex h-full min-h-0 flex-col" data-record-tabs>
		<div
			v-if="!ready"
			class="flex shrink-0 items-center gap-5 border-b px-[--page-gutter] py-2"
			data-record-tabs-skeleton
		>
			<Skeleton v-for="n in 4" :key="n" class="h-4 w-16 rounded-4" />
		</div>
		<div
			v-else-if="stripTabs.length"
			ref="stripRoot"
			class="shrink-0 px-[--page-gutter]"
			@pointerdown="pointerPressed = true"
			@pointercancel="pointerPressed = false"
			@pointerleave="pointerPressed = false"
			@click="pointerPressed = false"
		>
			<Tabs
				:modelValue="active"
				:tabs="stripTabs"
				@update:modelValue="emit('select', String($event))"
			/>
		</div>

		<div
			v-for="entry in mounted"
			v-show="entry.item.name === active"
			:key="entry.item.name"
			class="min-h-0 flex-1 overflow-y-auto"
			:data-record-tab="entry.item.name"
			@focusin="focused.set(entry.item.name, $event.target as HTMLElement)"
		>
			<component
				:is="entry.item.component"
				v-if="entry.item.component"
				v-bind="{ ...entry.item.props, page }"
			/>
			<slot v-else-if="entry.item.name === DETAILS_TAB" name="details" />
			<p v-else class="py-10 text-center text-base text-ink-gray-5">
				{{ __("Nothing here yet.") }}
			</p>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { Skeleton, Tabs } from "frappe-ui";
import type { ResolvedItem } from "@/recordPage/surface";
import type { RecordPageApi, TabItem } from "@/recordPage/types";
import { __ } from "@/i18n";
import { DETAILS_TAB } from "./recordTabs";

const props = defineProps<{
	tabs: ResolvedItem<TabItem>[];
	active: string;
	ready: boolean;
	page: RecordPageApi;
	/** True once when the page placed focus itself on the move to this tab. */
	claimsFocus?: (name: string) => boolean;
}>();

const emit = defineEmits<{ select: [name: string] }>();

const visited = reactive(new Set<string>());
const focused = new Map<string, HTMLElement>();
const stripRoot = ref<HTMLElement | null>(null);
let pointerPressed = false;

// `iconLeft`: frappe-ui draws a tab with `icon` and a label as an icon alone.
const stripTabs = computed(() =>
	props.tabs
		.filter((entry) => !entry.hidden)
		.map(({ item }) => ({ value: item.name, label: item.label, iconLeft: item.icon }))
);

// A tab a script hides keeps its body, as a switch does.
const mounted = computed(() => props.tabs.filter((entry) => visited.has(entry.item.name)));

watch(
	[() => props.page, () => props.active],
	([page, name], previous) => {
		if (page !== previous?.[0]) forgetBodies();
		if (name) visited.add(name);
		if (previous?.[1] !== undefined && name) returnFocus(name, previous[1]);
	},
	{ immediate: true }
);

function forgetBodies() {
	visited.clear();
	focused.clear();
}

// Arrow keys on the strip keep focus there; focus elsewhere on the page stays where the reader put it.
function returnFocus(name: string, left: string) {
	const pointer = pointerPressed;
	pointerPressed = false;
	if (props.claimsFocus?.(name) || !mayTakeFocus(pointer, left)) return;
	requestAnimationFrame(() => {
		const target = focused.get(name);
		if (target?.isConnected && name === props.active) target.focus({ preventScroll: true });
	});
}

function mayTakeFocus(pointer: boolean, left: string) {
	const current = document.activeElement;
	if (pointer) return true;
	if (stripRoot.value?.contains(current)) return false;
	if (!current || current === document.body) return true;
	return current.closest("[data-record-tab]")?.getAttribute("data-record-tab") === left;
}
</script>
