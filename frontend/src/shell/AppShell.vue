<!--
  The shell's own surface.

  The line the contribution contract draws: the shell owns everything that must look
  the same in every app; an app contributes only INSIDE a routed view. There is no
  contributeSidebarItem, no contributeCommand, no shell-level hook of any kind
  (#42072).

  Both halves go to the rail, and that is why they are one prop pair rather than two
  components: a rail item of type `Sidebar` is what makes an item LINKED (#42227), and it
  resolves its own destination out of the sidebar it opens — so the rail cannot draw the
  rail without holding the sidebars too. The panel that shows one is this file's, not the
  rail's: which sidebar is open is a fact about the ADDRESS, and the address outlives any
  row on the rail (#42421).

  Navigation lives here, one level above the rail, because it is not the rail's. A save
  returns the WHOLE `{rail, sidebars}` for the prefix and the client swaps it in wholesale
  (#42363) — so hiding a rail item of type `Sidebar` changes which sidebars are reachable, and
  the one place that knows about both is this one. `boot.navigation` is kept in step for anything
  that reads boot directly; the reactive copy is what renders.

  The item context is composed here for the same reason. It is composed once per LIST, and
  since the panel draws rows out of the same payload the rail does, two contexts would be two
  answers to `renderingOf` for one row — and a `Sidebar` item resolves through the sidebars,
  so the two would not even be equal.
-->
<template>
	<div class="flex h-screen w-screen bg-surface-white text-ink-gray-9">
		<AppRail
			:items="navigation.rail"
			:context="contexts.rail"
			:current="current.railKey"
			:arrangeable="!!boot.app"
			@arrange="arrangeRail"
		/>
		<AppSidebar
			v-if="panel"
			:key="panel.address"
			:address="panel.address"
			:items="panel.items"
			:context="panel.context"
			:title="panel.title"
			:current="current.rowKey"
			arrangeable
			@arrange="arrangeSidebar"
		/>
		<main class="flex min-w-0 flex-1 flex-col">
			<RouterView />
		</main>
		<ArrangementEditor
			v-if="arranging"
			:container="arranging.container"
			:address="arranging.address"
			:title="arranging.title"
			@saved="replace"
			@close="arranging = null"
		/>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, ref } from "vue";
import { RouterView, useRoute, useRouter } from "vue-router";
import type { Addresses } from "@/addresses";
import type { Boot, Navigation, NavigationItem } from "@/boot";
import type { Container } from "@/arrangement";
import { itemContext } from "@/navigation/context";
import {
	currentFrom,
	navigationDestinations,
	type NavigationContexts,
} from "@/navigation/current";
import AppRail from "./AppRail.vue";
import AppSidebar from "./AppSidebar.vue";
import ArrangementEditor from "./ArrangementEditor.vue";

const boot = inject<Boot>("boot")!;
const addresses = inject<Addresses>("addresses")!;
const router = useRouter();
const route = useRoute();

// Which container is being arranged, or nothing. One editor rather than one per surface: the
// three endpoints take the container as an argument, so a second component would only be the
// same dialog with a different string baked in (#42363).
const arranging = ref<{ container: Container; address: string; title: string } | null>(null);
const navigation = ref<Navigation>(boot.navigation ?? { rail: [], sidebars: {} });

// One context per container. The rail and each sidebar are separate LISTS, and a context is
// composed once per list rather than once per row — `Module Contents` is what makes that more
// than bookkeeping, since it measures "what is left of this module" against `context.items`.
// A sidebar row handed the rail's context would answer that question about the rail.
const contexts = computed<NavigationContexts>(() => {
	const compose = (items: NavigationItem[]) =>
		itemContext(boot, addresses, router, items, navigation.value.sidebars);

	return {
		rail: compose(navigation.value.rail),
		sidebars: Object.fromEntries(
			Object.entries(navigation.value.sidebars).map(([address, rows]) => [
				address,
				compose(rows),
			])
		),
	};
});

// Every route navigation can be standing on. Off the PAYLOAD, so it survives a navigation:
// building it costs a route resolution per row and the framework's own prefix carries 194 of
// them (#42362), which is not a bill to pay on every click.
const destinations = computed(() =>
	navigationDestinations(navigation.value.rail, navigation.value.sidebars, contexts.value)
);

// And this is recomputed on every navigation, which is the whole design: nothing here is set
// by a click. It is a walk over resolved paths, with no router in it.
const current = computed(() => currentFrom(destinations.value, route.path));

// The panel, or nothing. `current.sidebar` is only ever a key a rail item's renderer read out
// of this same payload, so the rows are there — the row count is checked anyway because an
// empty panel is the one state #42357 ruled out, and it is fenced twice before this: a sidebar
// that resolved to nothing is absent from the payload rather than empty (#42356), and the
// `Sidebar` renderer then draws no rail item to open it.
const panel = computed(() => {
	const address = current.value.sidebar;
	const items = address ? navigation.value.sidebars[address] : undefined;
	if (!address || !items?.length) return null;

	const owner = navigation.value.rail.find((item) => item.key === current.value.railKey);

	return {
		address,
		items,
		context: contexts.value.sidebars[address],
		// The AUTHORED label and nothing else. `labelOf`'s fallbacks are all wrong for a
		// `Sidebar` item: its renderer offers none, and the last resort is `link_to`, which
		// here is the scrubbed address — a heading reading `module_def_accounts` is worse than
		// no heading, and the rail item above it is highlighted either way.
		title: owner?.label,
	};
});

function arrangeRail() {
	arranging.value = {
		container: "Rail",
		address: boot.app!,
		title: "Arrange this rail",
	};
}

function arrangeSidebar() {
	if (!panel.value) return;
	arranging.value = {
		container: "Sidebar",
		address: panel.value.address,
		title: "Arrange this sidebar",
	};
}

function replace(next: Navigation) {
	navigation.value = next;
	boot.navigation = next;
}
</script>
