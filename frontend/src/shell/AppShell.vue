<!--
  The shell's own surface: rail, panel, routed view and the arrangement editor. Navigation lives
  here because a save replaces the whole `{rail, sidebars}`, and the open sidebar is a fact about the address.
-->
<template>
	<div class="flex h-screen w-screen bg-surface-base text-ink-gray-9">
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

// One editor for both containers; the endpoints take the container as an argument.
const arranging = ref<{ container: Container; address: string; title: string } | null>(null);
const navigation = ref<Navigation>(boot.navigation ?? { rail: [], sidebars: {} });

// One context per container: `Module Contents` measures against `context.items`, so a
// sidebar row handed the rail's list would answer about the rail.
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

// A reader's own disclosures, one store per container: the rail by its app, a panel by its address.
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

// Off the payload, not per navigation: it costs a route resolution per row.
const destinations = computed(() =>
	navigationDestinations(navigation.value.rail, navigation.value.sidebars, contexts.value)
);

// A ref off a watcher, not a computed: the resolution feeds itself, since the open panel is
// the next address's first preference and recording it is a write.
const current = ref<CurrentNavigation>({});

// The panel the address asked for, outranking the open one because a paste is deliberate.
const asked = ref<string | undefined>(undefined);

// `listen` fires on pops only, so this marks a back or a forward.
let popped = false;
const stopListening = router.options.history.listen(() => {
	popped = true;
});
onUnmounted(stopListening);

// What the address alone says, so the copy link names the panel only where it adds something.
const canonical = computed(() => currentFrom(destinations.value, route.path));

function resolve() {
	const path = route.path;
	// Most wanted first, each a tie-break only, so a stale or misspelled `?sidebar=` loses silently.
	const prefer = [asked.value, stamped(), current.value.sidebar, recallSidebar(path)].filter(
		(sidebar): sidebar is string => !!sidebar
	);

	current.value = currentFrom(destinations.value, path, prefer);
	const sidebar = current.value.sidebar;
	if (sidebar) {
		// Onto the entry, so back and forward return to the sidebar a page was read in. The
		// compare leaves a pop's own state alone, which its forward entries hang off.
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

// The parameter seeds the record, then leaves the address by `replace` with no second history entry.
watch(
	[() => route.fullPath, destinations],
	() => {
		// Repeated in the address it arrives as an array, which must still be consumed.
		const asking = route.query.sidebar;
		const named = Array.isArray(asking) ? asking[0] : asking;
		asked.value = typeof named === "string" ? named : undefined;

		resolve();

		if (asking !== undefined) {
			const { sidebar: _consumed, ...query } = route.query;
			asked.value = undefined;
			// `hash` is not ours to drop. An aborted replace rejects, and the sidebar is recorded by then.
			router.replace({ path: route.path, query, hash: route.hash }).catch(() => {});
		}
	},
	{ immediate: true }
);

// The link to hand someone else; the parameter goes on only where it says something.
const shareLink = computed(() => {
	const sidebar = current.value.sidebar;
	const query =
		sidebar && sidebar !== canonical.value.sidebar ? { ...route.query, sidebar } : route.query;

	const to = router.resolve({ path: route.path, query, hash: route.hash });
	return new URL(to.href, window.location.origin).href;
});

// The panel, or nothing. An empty sidebar is absent from the payload; the count is the last fence.
const panel = computed(() => {
	const address = current.value.sidebar;
	const items = address ? navigation.value.sidebars[address] : undefined;
	if (!address || !items?.length) return null;

	const owner = navigation.value.rail.find((item) => item.key === current.value.railKey);

	return {
		address,
		items,
		context: contexts.value.sidebars[address],
		// The authored label only: `labelOf`'s last resort is `link_to`, here the scrubbed address.
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
