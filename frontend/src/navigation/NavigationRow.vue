<!--
  One row of navigation and whatever hangs under it, shared by the rail and the panel.
  A row with no rendering is skipped but its children still draw, as the server does for orphans.
-->
<template>
	<li>
		<!-- A destination in this prefix. -->
		<RouterLink
			v-if="destination && 'to' in destination"
			:to="destination.to"
			:data-key="item.key"
			:data-sidebar="destination.sidebar"
			:aria-current="isCurrent ? 'page' : undefined"
			:class="[ROW, isCurrent && CURRENT]"
		>
			<Icon :name="item.icon" :reserve="reserve" />
			<span class="truncate">{{ label }}</span>
		</RouterLink>

		<!-- A destination outside this prefix: a full document load, so an `<a>`, never a `RouterLink`. -->
		<a
			v-else-if="destination && 'href' in destination"
			:href="destination.href"
			:data-key="item.key"
			:data-sidebar="destination.sidebar"
			:aria-current="isCurrent ? 'page' : undefined"
			:class="[ROW, isCurrent && CURRENT]"
		>
			<Icon :name="item.icon" :reserve="reserve" />
			<span class="truncate">{{ label }}</span>
		</a>

		<!-- Rows fetched on demand. A button, not a link: it goes nowhere. -->
		<button
			v-else-if="expander"
			type="button"
			:data-key="item.key"
			:aria-expanded="String(expanded)"
			:class="ROW"
			@click="expand"
		>
			<Icon :name="item.icon" :reserve="reserve" />
			<span class="truncate">{{ label }}</span>
		</button>

		<!-- A heading; a collapsible one is a control, so a button. -->
		<component
			v-else-if="heading"
			:is="collapsible ? 'button' : 'p'"
			:type="collapsible ? 'button' : undefined"
			:data-key="item.key"
			:aria-expanded="collapsible ? String(open) : undefined"
			:class="HEADING"
			@click="collapsible ? toggle() : undefined"
		>
			{{ label }}
		</component>

		<ul v-if="node.children.length && open" class="ml-2 border-l border-outline-gray-2 pl-1">
			<NavigationRow
				v-for="child in node.children"
				:key="child.item.key"
				:node="child"
				:context="context"
				:current="current"
				:reserve="reserve"
				:sections="sections"
			/>
		</ul>

		<!-- Expanded rows sit at this row's own level: an overflow of the list, not its children.
					 No `sections`: fetched rows are not in the payload, so a toggle against one would be pruned. -->
		<NavigationRow
			v-for="child in expandedNodes"
			:key="child.item.key"
			:node="child"
			:context="context"
			:current="current"
			:reserve="reserve"
		/>
	</li>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { buildTree, containsKey, type ItemNode } from "@/navigation/tree";
import type { SectionMemory } from "@/navigation/sectionMemory";
import { labelOf, renderingOf } from "@/navigation/registry";
import Icon from "@/icons/Icon.vue";
import type { ItemContext } from "@/navigation/types";

const ROW =
	"flex w-full items-center gap-2 truncate rounded px-2 py-1 text-left text-sm text-ink-gray-7 hover:bg-surface-gray-2";
// A step past the hover shade, or the current row and the hovered row look the same. Bound
// explicitly so `RouterLink`'s own `aria-current` is suppressed and only one row is marked.
const CURRENT = "bg-surface-gray-3 font-medium text-ink-gray-9";
const HEADING =
	"w-full truncate px-2 pb-0.5 pt-3 text-left text-xs font-medium uppercase text-ink-gray-5";

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

// Re-derived, not assigned: a save returns the app's own layer, so the same key can come
// back with a different `keep_closed` while this component survives.
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

// A new context is a new list, and what an expansion showed was measured against the old
// one, so it collapses; `generation` keeps a fetch left in flight from putting rows back.
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
