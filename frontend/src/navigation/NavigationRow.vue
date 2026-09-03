<!--
  One row of navigation, and whatever hangs under it.

  The rail and the sidebar panel are two presentations of one model (charter point 1), so
  they draw their rows with one component. It was `shell/RailItem.vue` until the panel
  arrived (#42421) and there was a second consumer to name it for.

  Recursive, because `parent_key` puts no limit on depth and a two-level component would
  silently swallow the third — the same class of quiet drop the tree builder's cycle guard
  exists to prevent. Nothing here decides what a row DOES: it asks the renderer, and draws
  one of the four shapes it can come back with (`navigation/types.ts`).

  An icon is drawn on every shape that goes somewhere, and never on a heading; a heading
  that carries one has it ignored.

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
			:aria-current="isCurrent ? 'page' : undefined"
			:class="[ROW, isCurrent && CURRENT]"
		>
			<Icon :name="item.icon" :reserve="reserve" />
			<span class="truncate">{{ label }}</span>
		</RouterLink>

		<!-- A destination outside it. Following this is a full document load, so it is an
				 `<a>` and never a `RouterLink`: the router this document holds is scoped to one
				 prefix and cannot resolve the other (#42364). -->
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
			<Icon :name="item.icon" :reserve="reserve" />
			<span class="truncate">{{ label }}</span>
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
			<NavigationRow
				v-for="child in node.children"
				:key="child.item.key"
				:node="child"
				:context="context"
				:current="current"
				:reserve="reserve"
			/>
		</ul>

		<!-- Expanded rows sit at this row's OWN level, not under it. "N more" is an overflow
				 of the list it is in, so indenting what it reveals would say the module contains
				 the overflow row, which is backwards. -->
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
import { buildTree, type ItemNode } from "@/navigation/tree";
import { labelOf, renderingOf } from "@/navigation/registry";
import Icon from "@/icons/Icon.vue";
import type { ItemContext } from "@/navigation/types";

const ROW =
	"flex w-full items-center gap-2 truncate rounded px-2 py-1 text-left text-sm text-ink-gray-7 hover:bg-surface-gray-2";
// A step past `hover:bg-surface-gray-2` rather than the same shade, or a reader could not
// tell the row they are on from the row under the pointer.
//
// Marked on the row itself and not left to `router-link-active`: a linked rail item points at
// the first row INSIDE its sidebar, so its own link is inactive from the second row on. The
// explicit `aria-current` binding also SUPPRESSES the one `RouterLink` sets on an exactly
// active link, which is what keeps the count at one row — the rail and the panel can hold the
// same destination, and two independent highlights would light both.
const CURRENT = "bg-surface-gray-3 font-medium text-ink-gray-9";
const HEADING =
	"w-full truncate px-2 pb-0.5 pt-3 text-left text-xs font-medium uppercase text-ink-gray-5";

// `current` is the key of the one row the address is standing on, in THIS container
// (`navigation/current.ts`). It is passed down rather than computed here because exactly one
// row wins across the rail and the open panel together, and no row can know that alone.
//
// `reserve` is decided once for a whole container and handed to every row in it, so a
// container where only some rows carry an icon still reads as one list.
const props = defineProps<{
	node: ItemNode;
	context: ItemContext;
	current?: string;
	reserve?: boolean;
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
// A row with children and no destination of its own reads as a heading whether or not its
// renderer said `group`, which is what keeps an unrenderable parent from turning its
// children into an unexplained indent.
const heading = computed(
	() => (rendering.value && "group" in rendering.value) || props.node.children.length > 0
);

// `keep_closed` is what makes a section START closed; `collapsible` is what lets a reader
// close it. Neither is the same as "open", so a section that is neither stays open and has
// no control (#42227).
//
// The watch is on the SHIPPED value, not on the item: a reset returns the app's own layer
// (#42363), so the same key can come back with a different `keep_closed` while this
// component survives — `v-for` keys on the key — and the section would sit open or closed
// against what it now ships until a reload. Watching the value rather than the row is what
// keeps that distinct from a reader's own toggle, which changes `open` and never
// `keep_closed`, so a save cannot re-open what somebody just closed.
const open = ref(!item.value.keep_closed);

watch(
	() => item.value.keep_closed,
	(keepClosed) => {
		open.value = !keepClosed;
	}
);

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
