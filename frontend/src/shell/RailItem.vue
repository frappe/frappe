<!--
  One row on the rail, and whatever hangs under it.

  Recursive, because `parent_key` puts no limit on depth and a two-level component would
  silently swallow the third — the same class of quiet drop the tree builder's cycle guard
  exists to prevent. Nothing here decides what a row DOES: it asks the renderer, and draws
  one of the four shapes it can come back with (`navigation/types.ts`).

  A row with no rendering and no children is not drawn at all. That is #42228's degrade for
  a kind with no renderer, widened to every reason an item cannot be placed here — a
  `Module` under a non-modular prefix, a `Page` whose slug this prefix does not serve. Its
  children are still drawn, so a heading whose renderer is missing loses the heading and
  not its contents, which is the choice `_promote_orphans` already makes on the server.
-->
<template>
	<li>
		<!-- A destination in this prefix. -->
		<RouterLink
			v-if="destination && 'to' in destination"
			:to="destination.to"
			:data-key="item.key"
			:data-sidebar="destination.sidebar"
			:class="ROW"
		>
			{{ label }}
		</RouterLink>

		<!-- A destination outside it. Following this is a full document load, so it is an
				 `<a>` and never a `RouterLink`: the router this document holds is scoped to one
				 prefix and cannot resolve the other (#42364). -->
		<a
			v-else-if="destination && 'href' in destination"
			:href="destination.href"
			:data-key="item.key"
			:data-sidebar="destination.sidebar"
			:class="ROW"
		>
			{{ label }}
		</a>

		<!-- Rows that are not known until they are asked for. A BUTTON, not a link: it goes
				 nowhere, and a keyboard reader who meets it as a link has been told it does. -->
		<button
			v-else-if="expander"
			type="button"
			:data-key="item.key"
			:aria-expanded="String(expanded)"
			:class="ROW"
			@click="expand"
		>
			{{ label }}
		</button>

		<!-- A heading. Collapsible ones are a button, because a heading a reader can close is
				 a control; the rest are not, because most sections are decoration around a list
				 that should simply be visible. -->
		<component
			v-else-if="heading"
			:is="item.collapsible ? 'button' : 'p'"
			:type="item.collapsible ? 'button' : undefined"
			:data-key="item.key"
			:aria-expanded="item.collapsible ? String(open) : undefined"
			:class="HEADING"
			@click="item.collapsible ? (open = !open) : undefined"
		>
			{{ label }}
		</component>

		<ul v-if="node.children.length && open" class="ml-2 border-l border-outline-gray-2 pl-1">
			<RailItem
				v-for="child in node.children"
				:key="child.item.key"
				:node="child"
				:context="context"
			/>
		</ul>

		<!-- Expanded rows sit at this row's OWN level, not under it. "N more" is an overflow
				 of the list it is in, so indenting what it reveals would say the module contains
				 the overflow row, which is backwards. -->
		<RailItem
			v-for="child in expandedNodes"
			:key="child.item.key"
			:node="child"
			:context="context"
		/>
	</li>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { buildTree, type ItemNode } from "@/navigation/tree";
import { labelOf, renderingOf } from "@/navigation/registry";
import type { ItemContext } from "@/navigation/types";

const ROW =
	"flex w-full items-center truncate rounded px-2 py-1 text-left text-sm text-ink-gray-7 hover:bg-surface-gray-2";
const HEADING =
	"w-full truncate px-2 pb-0.5 pt-3 text-left text-xs font-medium uppercase text-ink-gray-5";

const props = defineProps<{ node: ItemNode; context: ItemContext }>();

const item = computed(() => props.node.item);
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
// A row with children and no destination of its own reads as a heading whether or not its
// renderer said `group`, which is what keeps an unrenderable parent from turning its
// children into an unexplained indent.
const heading = computed(
	() => (rendering.value && "group" in rendering.value) || props.node.children.length > 0
);

// `keep_closed` is what makes a section START closed; `collapsible` is what lets a reader
// close it. Neither is the same as "open", so a section that is neither stays open and has
// no control (#42227).
const open = ref(!item.value.keep_closed);

const expanded = ref(false);
const expandedNodes = ref<ItemNode[]>([]);

// A save returns the whole `{rail, sidebars}` and the shell swaps it in (#42363), which
// gives this a fresh context over a different list — while the component instance survives,
// because `v-for` keys on the item's key. What it revealed was "what is left of the module"
// measured against the OLD list, so a doctype the save has just added to the rail by hand
// would now be on screen twice. Collapsing is the honest state: the answer it was showing
// was computed about a list that no longer exists.
// Which expansion is current. A fetch left in flight by the reset below would otherwise
// land afterwards and put its rows back, with the button already saying collapsed — the
// same guard `contents.ts`, `List.vue` and `Record.vue` each carry, for the same reason.
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

	// Set before the await, so a second click while the first is in flight cannot fire a
	// second request against the same row.
	expanded.value = true;
	const mine = generation;

	try {
		const nodes = buildTree(await expander.value.expand());
		if (mine === generation) expandedNodes.value = nodes;
	} catch (error) {
		// Back to unexpanded, so it can be tried again. Expanding is the one thing on the
		// rail that costs a request, so it is the one thing that can fail from a dropped
		// connection rather than from a bad row.
		if (mine === generation) expanded.value = false;
		console.error(`[frappe] could not expand navigation item '${item.value.key}'`, error);
	}
}
</script>
