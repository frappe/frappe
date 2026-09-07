<!--
  One panel row on frappe-ui's `SidebarItem` and `SidebarSection`. The section the address is in
  opens itself and offers no control; a reader's toggle is remembered.
-->
<template>
	<!-- A heading with no destination: a section. Children mount only while it is open. -->
	<SidebarSection
		v-if="heading && !destination"
		:label="label"
		:collapsible="collapsible"
		:collapsed="!open"
		:data-key="item.key"
		@update:collapsed="toggle"
	>
		<template v-if="open">
			<SidebarRow
				v-for="child in node.children"
				:key="child.item.key"
				:node="child"
				:context="context"
				:current="current"
				:reserve="reserve"
				:sections="sections"
			/>
		</template>
	</SidebarSection>

	<template v-else>
		<!-- A destination in this prefix. -->
		<SidebarItem
			v-if="destination && 'to' in destination"
			:to="destination.to"
			:label="label"
			:active="isCurrent"
			:data-key="item.key"
			:data-sidebar="destination.sidebar"
		>
			<template #prefix><Icon :name="item.icon" :reserve="reserve" /></template>
		</SidebarItem>

		<!-- Outside this prefix: a full document load, so an `<a>`, which `SidebarItem` has no form for. -->
		<div v-else-if="destination && 'href' in destination" :data-key="item.key" :class="ROW">
			<a :href="destination.href" :class="ROW_TARGET">
				<span class="grid shrink-0 place-items-center">
					<Icon :name="item.icon" :reserve="reserve" />
				</span>
				<span class="ml-2 min-w-0 flex-1 truncate text-sm">{{ label }}</span>
			</a>
		</div>

		<!-- Rows fetched on demand; they land at this row's own level. -->
		<div v-else-if="expander" :data-key="item.key" :class="ROW">
			<button type="button" :class="ROW_TARGET" :aria-expanded="expanded" @click="expand">
				<span class="grid shrink-0 place-items-center">
					<Icon :name="item.icon" :reserve="reserve" />
				</span>
				<span class="ml-2 min-w-0 flex-1 truncate text-sm">{{ label }}</span>
			</button>
		</div>

		<!-- A heading with a destination: its children indent under it by hand. -->
		<div
			v-if="node.children.length && open"
			class="ml-3 flex flex-col gap-0.5 border-l border-outline-gray-2 pl-1"
		>
			<SidebarRow
				v-for="child in node.children"
				:key="child.item.key"
				:node="child"
				:context="context"
				:current="current"
				:reserve="reserve"
				:sections="sections"
			/>
		</div>

		<SidebarRow
			v-for="child in expandedNodes"
			:key="child.item.key"
			:node="child"
			:context="context"
			:current="current"
			:reserve="reserve"
		/>
	</template>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { SidebarItem, SidebarSection } from "frappe-ui";
import { buildTree, containsKey, type ItemNode } from "@/navigation/tree";
import type { SectionMemory } from "@/navigation/sectionMemory";
import { labelOf, renderingOf } from "@/navigation/registry";
import Icon from "@/icons/Icon.vue";
import type { ItemContext } from "@/navigation/types";

// `SidebarItem`'s own classes, for the two rows it has no form for. Neither is ever current.
const ROW = "flex h-7 items-center rounded-4 text-ink-gray-6 transition hover:bg-surface-gray-2";
const ROW_TARGET =
	"flex h-full min-w-0 flex-1 items-center rounded-4 pl-2 text-left focus-visible:ring-0 focus-visible:focus-ring";

// `current` is passed down: one row wins across the rail and the open panel together.
// `reserve` is decided once per container.
const props = defineProps<{
	node: ItemNode;
	context: ItemContext;
	current?: string;
	reserve?: boolean;
	sections?: SectionMemory;
}>();

const item = computed(() => props.node.item);
const isCurrent = computed(() => !!props.current && props.current === item.value.key);
const rendering = computed(() => renderingOf(item.value, props.context));
const label = computed(() => labelOf(item.value, props.context));

const destination = computed(() => {
	const value = rendering.value;
	return value && ("to" in value || "href" in value) ? value : null;
});
const expander = computed(() => {
	const value = rendering.value;
	return value && "expand" in value ? value : null;
});
// Children with no destination read as a heading whether or not the renderer said `group`.
const heading = computed(
	() => (rendering.value && "group" in rendering.value) || props.node.children.length > 0
);

// `keep_closed` starts a section closed; `collapsible` lets a reader close it. Neither is "open".
const shippedOpen = computed(() => !item.value.keep_closed);

// The one section the address is standing in opens itself, transiently and writing nothing.
const holdsCurrent = computed(() => !!props.current && containsKey(props.node, props.current));

// No control while the address is inside: the section may not shut over the row you are on.
const collapsible = computed(() => !!item.value.collapsible && !holdsCurrent.value);

/** Where this section rests when the address is not inside it. */
function settled(): boolean {
	return props.sections?.recall(item.value.key) ?? shippedOpen.value;
}

const open = ref(holdsCurrent.value || settled());

// Re-derived, not assigned: a save can bring the same key back with a different `keep_closed`.
watch([() => item.value.keep_closed, holdsCurrent], () => {
	open.value = holdsCurrent.value || settled();
});

/** A click on the heading, the one thing here that writes. */
function toggle() {
	open.value = !open.value;
	props.sections?.remember(item.value.key, open.value);
}

const expanded = ref(false);
const expandedNodes = ref<ItemNode[]>([]);

// A new context is a new list, so an expansion measured against the old one collapses;
// `generation` keeps a fetch left in flight from putting rows back.
let generation = 0;

watch(
	() => props.context,
	() => {
		generation += 1;
		expanded.value = false;
		expandedNodes.value = [];
	}
);

async function expand() {
	if (!expander.value || expanded.value) return;

	// Set before the await, so a second click cannot fire a second request.
	expanded.value = true;
	const mine = generation;

	try {
		const nodes = buildTree(await expander.value.expand());
		if (mine === generation) expandedNodes.value = nodes;
	} catch (error) {
		// Back to unexpanded, so it can be tried again.
		if (mine === generation) expanded.value = false;
		console.error(`[frappe] could not expand navigation item '${item.value.key}'`, error);
	}
}
</script>
