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
			:share-link="shareLink"
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
import { computed, inject, ref, watch } from "vue";
import { RouterView, useRoute, useRouter } from "vue-router";
import type { Addresses } from "@/addresses";
import type { Boot, Navigation, NavigationItem } from "@/boot";
import type { Container } from "@/arrangement";
import { itemContext } from "@/navigation/context";
import {
	currentFrom,
	navigationDestinations,
	type CurrentNavigation,
	type NavigationContexts,
} from "@/navigation/current";
import { recallPanel, rememberPanel } from "@/navigation/panelMemory";
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

// The panel the reader is in, resolved on every arrival however they got there — click, paste,
// reload, back. Still nothing set by a click: this is a walk over resolved paths, and the only
// thing the reader's history contributes is which of several EQUALLY correct panels to pick
// (#42432).
//
// A ref driven by a watcher rather than a computed, because the resolution feeds itself: the
// panel open now is the first preference for the next address, and remembering the answer is a
// write. A computed that stored its own result would run on every read.
const current = ref<CurrentNavigation>({});

// The panel named in the address, most-wanted preference and consumed once. A pasted `?panel=`
// is a deliberate act, so it outranks whatever this tab happens to have open.
const asked = ref<string | undefined>(undefined);

// What the address alone says, with no reader in it — the cold-load answer. Used to keep the
// copy link honest: naming the panel a stranger would land in anyway says nothing.
const canonical = computed(() => currentFrom(destinations.value, route.path));

function resolve() {
	const path = route.path;
	// Most wanted first: the panel just asked for, then the one already open, then whatever
	// this tab last resolved here. Each is only a tie-break — a panel that does not cover the
	// address, or covers it less deeply than another, loses regardless, which is how a
	// `?panel=` that is stale, misspelled or filtered away by permissions degrades silently.
	const prefer = [asked.value, current.value.sidebar, recallPanel(path)].filter(
		(panel): panel is string => !!panel
	);

	current.value = currentFrom(destinations.value, path, prefer);
	if (current.value.sidebar) rememberPanel(path, current.value.sidebar);
}

// The parameter seeds the same per-tab record ordinary browsing fills, then leaves the address.
// `replace`, so the clean URL is not a second history entry the back button has to walk
// through; and the record is already written, so back and reload still land in the same panel.
watch(
	[() => route.fullPath, destinations],
	() => {
		// Repeated in the address (`?panel=a&panel=b`) it arrives as an array. Nothing we hand
		// out looks like that, but it still has to be consumed rather than left in the bar
		// forever, so the first one is read and the rest go with it.
		const panel = route.query.panel;
		const named = Array.isArray(panel) ? panel[0] : panel;
		asked.value = typeof named === "string" ? named : undefined;

		resolve();

		if (panel !== undefined) {
			const { panel: _consumed, ...query } = route.query;
			asked.value = undefined;
			// `hash` survives: it addresses a place within the page, which has nothing to do
			// with the panel and is not ours to drop. An aborted or redirected replace rejects,
			// and there is nothing to do about it — the panel is already resolved and recorded,
			// so the only loss is a parameter left in the bar.
			router.replace({ path: route.path, query, hash: route.hash }).catch(() => {});
		}
	},
	{ immediate: true }
);

// The link to hand someone else, or nothing to offer. The parameter goes on only where it says
// something: in the canonical panel it is a tautology, the rule already set for `?from=` on
// re-entering its own prefix.
const shareLink = computed(() => {
	const panel = current.value.sidebar;
	const query =
		panel && panel !== canonical.value.sidebar ? { ...route.query, panel } : route.query;

	const to = router.resolve({ path: route.path, query, hash: route.hash });
	return new URL(to.href, window.location.origin).href;
});

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
