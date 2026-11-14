<!--
  The rail on frappe-ui's `SidebarRail`: an icon column. With `chrome`, the app tile that opens the app menu comes first.
  A heading has no icon form, so its children draw flat; rows fetched on demand are not drawn.
-->
<template>
	<SidebarRail>
		<template v-if="chrome">
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
				<UtilitySlots form="cell" />
				<Divider flex-item />
			</div>
		</template>

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

					<!-- An action: a button, never current and never linked to a sidebar. -->
					<ActCell v-else-if="'act' in cell" :cell="cell" />

					<!-- Off this prefix: a full document load, so an `<a>` with `SidebarRailItem`'s classes.
					     Never current: `current` is a route. -->
					<Tooltip v-else :text="cell.label" side="right">
						<a
							:href="cell.href"
							:target="cell.external ? '_blank' : undefined"
							:rel="cell.external ? 'noopener' : undefined"
							data-slot="sidebar-rail-item"
							:class="CELL"
							:aria-label="cell.ariaLabel ?? cell.label"
						>
							<Icon v-if="cell.icon" :name="cell.icon" />
							<span v-else class="text-sm font-medium">{{
								cell.label.charAt(0)
							}}</span>
							<span
								v-if="cell.external"
								class="lucide-arrow-up-right absolute -right-1 -top-1 size-3 text-ink-gray-5"
								aria-hidden="true"
							/>
						</a>
					</Tooltip>
				</div>
			</nav>
		</ScrollArea>

		<!-- The person's cell, pinned to the foot by the `ScrollArea`'s `flex-1` above it. -->
		<div v-if="chrome" class="mt-3 flex shrink-0 items-center justify-center">
			<UserMenu />
		</div>
		<div v-if="$slots.foot" class="mt-3 flex shrink-0 items-center justify-center">
			<slot name="foot" />
		</div>
	</SidebarRail>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { RouteLocationRaw } from "vue-router";
import { Divider, Dropdown, SidebarRail, SidebarRailItem, ScrollArea, Tooltip } from "frappe-ui";
import type { NavigationItem } from "@/boot";
import { __ } from "@/i18n";
import Icon from "@/icons/Icon.vue";
import { isActAvailable } from "./actRow";
import { labelOf, renderingOf } from "@/navigation/registry";
import type { ItemNode } from "@/navigation/tree";
import { useItemTree } from "@/navigation/useItemTree";
import type { ItemContext } from "@/navigation/types";
import { useAppMenu } from "./appMenu";
import ActCell from "./RailActCell.vue";
import UserMenu from "./UserMenu.vue";
import UtilitySlots from "./UtilitySlots.vue";

type Cell = { key: string; label: string; icon?: string; sidebar?: string } & (
	| { to: RouteLocationRaw }
	| { href: string; external?: boolean; ariaLabel?: string }
	| { act: string; value?: unknown }
);

const TILE =
	"flex size-7 items-center justify-center rounded-[7px] transition focus-visible:ring-0 focus-visible:focus-ring";
const LETTER_TILE =
	"bg-surface-gray-3 text-sm font-medium text-ink-gray-8 hover:bg-surface-gray-4";
// `SidebarRailItem`'s own inactive tile.
const CELL =
	"relative flex size-7 shrink-0 items-center justify-center rounded-[7px] bg-surface-gray-3 text-base transition focus-visible:ring-0 focus-visible:focus-ring";
// The shell decides `current`, one row across rail and panel; a context is composed once per list.
const props = withDefaults(
	defineProps<{
		items: NavigationItem[];
		context: ItemContext;
		current?: string;
		chrome?: boolean;
	}>(),
	{ chrome: true }
);

const { boot, appTitle, menu, loadApps } = useAppMenu();

const tree = useItemTree(() => props.items, "the rail");

// Depth-first and flat: a heading contributes its children and nothing else.
const cells = computed(() => {
	const out: Cell[] = [];
	const walk = (nodes: ItemNode[]) => {
		for (const node of nodes) {
			const cell = cellOf(node.item);
			if (cell && !("act" in cell && !isActAvailable(cell.act))) out.push(cell);
			walk(node.children);
		}
	};
	walk(tree.value);
	return out;
});

function cellOf(item: NavigationItem): Cell | null {
	const rendering = renderingOf(item, props.context);
	if (!rendering || !("to" in rendering || "href" in rendering || "act" in rendering))
		return null;

	const cell = { key: item.key, label: labelOf(item, props.context), icon: item.icon };
	if ("act" in rendering) return { ...cell, ...rendering };
	return "to" in rendering
		? { ...cell, to: rendering.to, sidebar: rendering.sidebar }
		: {
				...cell,
				href: rendering.href,
				external: rendering.external,
				// Built here, with the label, so it is redone whenever the label is: the cell's `v-memo` sees a new cell.
				ariaLabel: rendering.external
					? __("{0} (opens in a new tab)", [cell.label])
					: undefined,
				sidebar: rendering.sidebar,
		  };
}
</script>
