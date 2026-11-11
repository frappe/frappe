<!--
  The rail on frappe-ui's `SidebarRail`: an icon column with the app tile first, which opens the app menu.
  A heading has no icon form, so its children draw flat; rows fetched on demand are not drawn.
-->
<template>
	<SidebarRail>
		<div class="mb-3 flex shrink-0 items-center justify-center">
			<!-- A raw button: `Dropdown` cannot reach a trigger through `SidebarRailItem`'s `Tooltip`. -->
			<Dropdown :options="menu" side="right" align="start">
				<button
					type="button"
					data-key="app-menu"
					@pointerenter="loadApps"
					@focus="loadApps"
					:class="[TILE, boot.app_logo ? 'hover:opacity-90' : LETTER_TILE]"
					:aria-label="__('{0} menu', [appTitle])"
				>
					<img
						v-if="boot.app_logo"
						:src="boot.app_logo"
						alt=""
						class="size-7 rounded-[7px]"
					/>
					<span v-else>{{ appTitle.charAt(0).toUpperCase() }}</span>
				</button>
			</Dropdown>
		</div>

		<div class="mb-3 flex shrink-0 flex-col items-center gap-3 self-stretch">
			<Divider flex-item />
			<Tooltip side="right">
				<template #content>
					<span class="flex items-center gap-2 [&_[data-slot=key]]:text-ink-gray-4">
						{{ __("Search") }} <KeyboardShortcut combo="Mod+K" />
					</span>
				</template>
				<button
					type="button"
					data-key="palette-trigger"
					:class="TRIGGER"
					:aria-label="__('Search')"
					aria-keyshortcuts="Control+K Meta+K"
					@click="openPalette"
				>
					<span class="lucide-search size-4" aria-hidden="true" />
				</button>
			</Tooltip>
			<Divider flex-item />
		</div>

		<!-- Stretched over `SidebarRail`'s own padding, so the scrollbar sits on the rail's edge. -->
		<ScrollArea class="-mx-[11px] min-h-0 flex-1 self-stretch" viewportClass="px-[11px]">
			<nav class="flex flex-col items-center gap-3" :aria-label="appTitle">
				<!-- `SidebarRailItem` puts attributes on its link, so the test hooks sit on a wrapper. Its slot
				     reads the loop variable, so without `v-memo` a route change redraws every cell. -->
				<div
					v-for="cell in cells"
					:key="cell.key"
					v-memo="[cell, cell.key === current]"
					:data-key="cell.key"
					:data-sidebar="cell.sidebar"
				>
					<SidebarRailItem
						v-if="'to' in cell"
						:route="cell.to"
						:label="cell.label"
						:active="cell.key === current"
					>
						<Icon v-if="cell.icon" :name="cell.icon" />
						<span v-else class="text-sm font-medium">{{ cell.label.charAt(0) }}</span>
					</SidebarRailItem>

					<!-- Off this prefix: a full document load, so an `<a>` with `SidebarRailItem`'s classes.
					     Never current: `current` is a route. -->
					<Tooltip v-else :text="cell.label" side="right">
						<a
							:href="cell.href"
							data-slot="sidebar-rail-item"
							:class="CELL"
							:aria-label="cell.label"
						>
							<Icon v-if="cell.icon" :name="cell.icon" />
							<span v-else class="text-sm font-medium">{{
								cell.label.charAt(0)
							}}</span>
						</a>
					</Tooltip>
				</div>
			</nav>
		</ScrollArea>

		<!-- The person's cell, pinned to the foot by the `ScrollArea`'s `flex-1` above it. -->
		<div class="mt-3 flex shrink-0 items-center justify-center">
			<UserMenu />
		</div>
	</SidebarRail>
</template>

<script setup lang="ts">
import { computed, h, inject, shallowRef } from "vue";
import type { RouteLocationRaw } from "vue-router";
import {
	Divider,
	Dropdown,
	KeyboardShortcut,
	SidebarRail,
	SidebarRailItem,
	ScrollArea,
	Tooltip,
	type DropdownOptions,
} from "frappe-ui";
import type { Boot, NavigationItem } from "@/boot";
import { __ } from "@/i18n";
import Icon from "@/icons/Icon.vue";
import { labelOf, renderingOf } from "@/navigation/registry";
import type { ItemNode } from "@/navigation/tree";
import { useItemTree } from "@/navigation/useItemTree";
import type { ItemContext } from "@/navigation/types";
import AppLogo from "./AppLogo.vue";
import { menuApps } from "./appSwitchOrder";
import { openPalette } from "./palette";
import type { PlacesApp } from "./palettePlaces";
import { loadDocument } from "./tabKeepAlive";
import { shellMenu } from "./shellActs";
import UserMenu from "./UserMenu.vue";

type Cell = { key: string; label: string; icon?: string; sidebar?: string } & (
	| { to: RouteLocationRaw }
	| { href: string }
);

const TILE =
	"flex size-7 items-center justify-center rounded-[7px] transition focus-visible:ring-0 focus-visible:focus-ring";
const LETTER_TILE =
	"bg-surface-gray-3 text-sm font-medium text-ink-gray-8 hover:bg-surface-gray-4";
// `SidebarRailItem`'s own inactive tile.
const CELL =
	"relative flex size-7 shrink-0 items-center justify-center rounded-[7px] bg-surface-gray-3 text-base transition focus-visible:ring-0 focus-visible:focus-ring";
// `SidebarRailItem`'s `ghost` cell, whose own tooltip would put the key on a second line.
const TRIGGER =
	"relative flex size-7 shrink-0 items-center justify-center rounded-4 text-base text-ink-gray-8 transition hover:bg-surface-gray-3 focus-visible:ring-0 focus-visible:focus-ring";

// The shell decides `current`, one row across rail and panel; a context is composed once per list.
const props = defineProps<{
	items: NavigationItem[];
	context: ItemContext;
	current?: string;
}>();

const boot = inject<Boot>("boot")!;

const appTitle = computed(() => boot.app_title ?? boot.app!);

const tree = useItemTree(() => props.items, "the rail");

// Depth-first and flat: a heading contributes its children and nothing else.
const cells = computed(() => {
	const out: Cell[] = [];
	const walk = (nodes: ItemNode[]) => {
		for (const node of nodes) {
			const cell = cellOf(node.item);
			if (cell) out.push(cell);
			walk(node.children);
		}
	};
	walk(tree.value);
	return out;
});

function cellOf(item: NavigationItem): Cell | null {
	const rendering = renderingOf(item, props.context);
	if (!rendering || !("to" in rendering || "href" in rendering)) return null;

	const cell = { key: item.key, label: labelOf(item, props.context), icon: item.icon };
	return "to" in rendering
		? { ...cell, to: rendering.to, sidebar: rendering.sidebar }
		: { ...cell, href: rendering.href, sidebar: rendering.sidebar };
}

const APP_MENU = ["all_apps", "open_settings", "customize_sidebar", "copy_link", "about"];

// The apps come from `places`, asked for when the tile is reached, so a boot carries none and
// the palette's chunk stays out of the shell's load.
const places = shallowRef<PlacesApp[]>([]);
const menu = computed<DropdownOptions>(() => {
	const apps = menuApps(places.value, boot.app).map((app) => ({
		label: app.title,
		icon: logoOf(app),
		onClick: () => loadDocument(app.route),
	}));
	const actions = { group: "", hideLabel: true, options: shellMenu(APP_MENU) };
	return apps.length ? [{ group: "", hideLabel: true, options: apps }, actions] : [actions];
});

function loadApps() {
	void import("./palettePlaces")
		.then((module) => module.loadApps())
		.then((apps) => (places.value = apps))
		.catch(() => {});
}

// A functional component so the menu row draws the logo, not an icon name.
function logoOf(app: PlacesApp) {
	return () => h(AppLogo, { logo: app.logo, title: app.title, size: 16 });
}
</script>
