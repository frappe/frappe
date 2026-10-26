<!--
  The shell's own surface: rail, panel, routed view and the overlay slot. Navigation lives here
  because a save replaces the whole `{rail, sidebars}`, and the open sidebar is a fact about the address.
-->
<template>
	<DesktopShell
		:scroll="false"
		class="relative h-screen w-screen bg-surface-base text-ink-gray-9"
		:class="{ 'desk-shell': boot.app }"
	>
		<template v-if="boot.app" #rail>
			<RailColumn
				:items="navigation.rail"
				:context="contexts.rail"
				:current="current.railKey"
				:share-link="shareLink"
				@customize="customize.write('rail')"
			/>
		</template>

		<template v-if="boot.app" #sidebar>
			<SidebarPanel
				v-if="panel"
				:key="panel.address"
				:address="panel.address"
				:items="panel.items"
				:context="panel.context"
				:title="panel.title"
				:current="current.rowKey"
				:sections="sections[panel.address]"
				customizable
				@customize="customize.write('sidebar', panel.address)"
			/>
		</template>

		<main class="flex min-h-0 flex-1 flex-col [&>*]:min-h-0 [&>*]:flex-1">
			<RouterView />
		</main>

		<div v-if="!boot.app" class="absolute bottom-3 left-[11px] z-10" data-index-foot>
			<UserMenu />
		</div>

		<!-- The hash dialogs: one hash, one Dialog, above any page. -->
		<CustomizeSidebarDialog
			:target="customizing"
			@saved="replace"
			@close="customize.close()"
		/>

		<ShellSettingsDialog v-if="settingsOpened" />

		<ShellPalette v-if="paletteLoaded" />

		<!-- The open writer, here so a floating one outlives the page it was opened on. -->
		<ComposerWindow :user="boot.session.user" />

		<component
			:is="createDialog()"
			v-for="request in createRequests"
			:key="request.id"
			:request="request"
		/>

		<ActKeys />
		<PaletteKey />
		<ToastProvider />
		<!-- frappe-ui's imperative dialog stack; `page.dialog.confirm` and `danger` render here. -->
		<Dialogs />
	</DesktopShell>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, inject, onUnmounted, provide, ref, watch } from "vue";
import { RouterView, useRoute, useRouter } from "vue-router";
import { DesktopShell, Dialogs, ToastProvider } from "frappe-ui";
import { keepInHistory } from "@framework/ui/utils";
import type { Addresses } from "@/addresses";
import type { Boot, Navigation, NavigationItem } from "@/boot";
import { itemContext } from "@/navigation/context";
import {
	currentFrom,
	navigationDestinations,
	type CurrentNavigation,
	type NavigationContexts,
} from "@/navigation/current";
import { sidebarMemory } from "@/navigation/sidebarMemory";
import { sectionMemory } from "@/navigation/sectionMemory";
import ComposerWindow from "./ComposerWindow.vue";
import { closeCreates, createDialog, createRequests } from "./create";
import CustomizeSidebarDialog, { type CustomizeTarget } from "./CustomizeSidebarDialog.vue";
import { OpenSettingsKey } from "./openSettings";
import { paletteOpen } from "./palette";
import RailColumn from "./RailColumn.vue";
import SidebarPanel from "./SidebarPanel.vue";
import { useHashDialog } from "./useHashDialog";
import UserMenu from "./UserMenu.vue";

const ShellSettingsDialog = defineAsyncComponent(() => import("./ShellSettingsDialog.vue"));
// Keys wait for no paint, so their code stays out of the cold-load chunk.
const ActKeys = defineAsyncComponent(() => import("./actKeys").then((module) => module.ActKeys));
const PaletteKey = defineAsyncComponent(() =>
	import("./paletteKey").then((module) => module.PaletteKey)
);
const ShellPalette = defineAsyncComponent(() => import("./ShellPalette.vue"));

const boot = inject<Boot>("boot")!;
const addresses = inject<Addresses>("addresses")!;
const router = useRouter();
const route = useRoute();

watch(() => route.fullPath, closeCreates);

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

// A reader's own disclosures, one store per panel by its address. The rail draws no sections.
const sections = computed(() =>
	Object.fromEntries(
		Object.entries(navigation.value.sidebars).map(([address, rows]) => [
			address,
			sectionMemory(boot.session.user.name, `Sidebar:${address}`, rows),
		])
	)
);

const sidebarsByAddress = sidebarMemory(boot.session.user.name);

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
	const prefer = [
		asked.value,
		stamped(),
		current.value.sidebar,
		sidebarsByAddress.recall(path),
	].filter((sidebar): sidebar is string => !!sidebar);

	current.value = currentFrom(destinations.value, path, prefer);
	const sidebar = current.value.sidebar;
	if (sidebar) {
		// Onto the entry, so back and forward return to the sidebar a page was read in. The
		// compare leaves a pop's own state alone, which its forward entries hang off.
		if (stamped() !== sidebar) keepInHistory("sidebar", sidebar);
		if (!popped) sidebarsByAddress.remember(path, sidebar);
	}
	popped = false;
}

/** The sidebar stamped on the entry being shown, if it carries one. */
function stamped(): string | undefined {
	const sidebar = history.state?.sidebar;
	return typeof sidebar === "string" ? sidebar : undefined;
}

// The parameter seeds the record, then leaves the address by `replace` with no second history entry.
// Each navigation, not each address: a back can land on the same address stamped with another sidebar.
watch(
	[router.currentRoute, destinations],
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
// Built on the click: a link handed down as a value would redraw the rail on every route change.
function shareLink(): string {
	const sidebar = current.value.sidebar;
	const query =
		sidebar && sidebar !== canonical.value.sidebar ? { ...route.query, sidebar } : route.query;

	const to = router.resolve({ path: route.path, query, hash: route.hash });
	return new URL(to.href, window.location.origin).href;
}

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

// One dialog for both containers; the endpoints take the container as an argument.
const customize = useHashDialog("customize");

// `#customize/rail` or `#customize/sidebar/<address>`; anything else under the root is nothing.
const customizing = computed<CustomizeTarget | null>(() => {
	const [what, address] = customize.segments.value;
	if (what === "rail" && boot.app)
		return { container: "Rail", address: boot.app, title: "Customize sidebar" };
	if (what === "sidebar" && address && navigation.value.sidebars[address])
		return { container: "Sidebar", address, title: "Customize this sidebar" };
	return null;
});

const settings = useHashDialog("settings");
provide(OpenSettingsKey, (...segments) =>
	settings.write(...segments.map((segment) => segment ?? ""))
);

// Loaded on the first open, then kept, so a close plays the dialog's leave transition.
const settingsOpened = ref(false);
watch(settings.open, (isOpen) => isOpen && (settingsOpened.value = true), { immediate: true });

// Loaded on the first open, then kept, like the settings dialog.
const paletteLoaded = ref(false);
watch(paletteOpen, (isOpen) => isOpen && (paletteLoaded.value = true), { immediate: true });

function replace(next: Navigation) {
	navigation.value = next;
	boot.navigation = next;
}
</script>

<style scoped>
/* The content's left edge; the panel draws the other one, and drops it while collapsed. */
.desk-shell :deep([data-slot="desktop-shell-content"]) {
	@apply border-l border-outline-gray-1 bg-surface-base;
}
</style>
