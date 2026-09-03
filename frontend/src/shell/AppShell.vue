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
			:sections="sections.rail"
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
			:sections="sections.sidebars[panel.address]"
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
import { computed, inject, onUnmounted, ref, watch } from "vue";
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
import { recallSidebar, rememberSidebar } from "@/navigation/sidebarMemory";
import { sectionMemory } from "@/navigation/sectionMemory";
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

// A reader's own disclosures, one store per container and rebuilt when the payload is. A
// container is named by what the shell knows: the rail by its app, a panel by its address.
const sections = computed(() => ({
	rail: boot.app
		? sectionMemory(boot.user.name, `Rail:${boot.app}`, navigation.value.rail)
		: undefined,
	sidebars: Object.fromEntries(
		Object.entries(navigation.value.sidebars).map(([address, rows]) => [
			address,
			sectionMemory(boot.user.name, `Sidebar:${address}`, rows),
		])
	),
}));

// Every route navigation can be standing on. Off the PAYLOAD, so it survives a navigation:
// building it costs a route resolution per row and the framework's own prefix carries 194 of
// them (#42362), which is not a bill to pay on every click.
const destinations = computed(() =>
	navigationDestinations(navigation.value.rail, navigation.value.sidebars, contexts.value)
);

// A ref off a watcher, not a computed: the resolution feeds itself, since the panel open now
// is the next address's first preference and recording the answer is a write.
const current = ref<CurrentNavigation>({});

// The panel the address asked for, outranking the open one because a paste is deliberate.
const asked = ref<string | undefined>(undefined);

// Whether the navigation being resolved is a back or a forward: `listen` fires on pops
// only, and reports the direction.
let popped = false;
const stopListening = router.options.history.listen(() => {
	popped = true;
});
onUnmounted(stopListening);

// What the address alone says. Keeps the copy link honest: naming the panel a stranger lands
// in anyway says nothing.
const canonical = computed(() => currentFrom(destinations.value, route.path));

function resolve() {
	const path = route.path;
	// Most wanted first, and each a tie-break only — which is how a `?sidebar=` that is stale,
	// misspelled or filtered away by permissions loses and degrades silently.
	const prefer = [asked.value, stamped(), current.value.sidebar, recallSidebar(path)].filter(
		(sidebar): sidebar is string => !!sidebar
	);

	current.value = currentFrom(destinations.value, path, prefer);
	const sidebar = current.value.sidebar;
	if (sidebar) {
		// Onto the ENTRY, so back and forward return to the sidebar a page was read in. The
		// compare leaves a pop's own state alone, which is what its forward entries hang off.
		if (stamped() !== sidebar) history.replaceState({ ...history.state, sidebar }, "");
		if (!popped) rememberSidebar(path, sidebar);
	}
	popped = false;
}

/** The sidebar stamped on the entry being shown, if it carries one. */
function stamped(): string | undefined {
	const sidebar = history.state?.sidebar;
	return typeof sidebar === "string" ? sidebar : undefined;
}

// The parameter seeds the same record browsing fills, then leaves the address by `replace`, so
// the bar is clean without a second history entry for back to walk through.
watch(
	[() => route.fullPath, destinations],
	() => {
		// Repeated in the address it arrives as an array, which must still be consumed or it
		// sits in the bar for the rest of the session.
		const asking = route.query.sidebar;
		const named = Array.isArray(asking) ? asking[0] : asking;
		asked.value = typeof named === "string" ? named : undefined;

		resolve();

		if (asking !== undefined) {
			const { sidebar: _consumed, ...query } = route.query;
			asked.value = undefined;
			// `hash` addresses a place within the page, so it is not ours to drop. An aborted
			// or redirected replace rejects, and the sidebar is recorded by then regardless.
			router.replace({ path: route.path, query, hash: route.hash }).catch(() => {});
		}
	},
	{ immediate: true }
);

// The link to hand someone else. The parameter goes on only where it says something, matching
// the rule `?from=` already follows on re-entering its own prefix.
const shareLink = computed(() => {
	const sidebar = current.value.sidebar;
	const query =
		sidebar && sidebar !== canonical.value.sidebar ? { ...route.query, sidebar } : route.query;

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
