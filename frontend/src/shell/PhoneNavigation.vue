<!-- The phone navigation: a tab bar at the foot and a bottom sheet of tiles and sidebar rows. -->
<template>
	<MobileNav
		ref="bar"
		:aria-label="__('Navigation')"
		class="fixed inset-x-0 bottom-0 z-30 pb-[env(safe-area-inset-bottom,0px)]"
		data-phone-nav
	>
		<MobileNavItem
			:label="__('Menu')"
			:active="open"
			aria-haspopup="dialog"
			:aria-expanded="open"
			@click="open = true"
		>
			<img v-if="boot.app_logo" :src="boot.app_logo" alt="" class="size-6 rounded-3" />
			<span
				v-else
				class="flex size-6 items-center justify-center rounded-3 bg-surface-gray-3 text-sm font-medium text-ink-gray-8"
				aria-hidden="true"
				>{{ appTitle.charAt(0).toUpperCase() }}</span
			>
		</MobileNavItem>
		<MobileNavItem :label="__('Search')" icon="lucide-search" @click="openPalette" />
		<UserMenu tab />
	</MobileNav>

	<BottomSheet v-model:open="open">
		<div class="flex flex-col pb-4" data-phone-sheet @click="closeOnAct">
			<NavigationHeader :utilities="false" />

			<nav
				class="flex shrink-0 gap-3 overflow-x-auto px-4 py-2"
				:aria-label="appTitle"
				data-phone-tiles
			>
				<div
					v-for="cell in cells"
					:key="cell.key"
					:data-key="cell.key"
					class="flex w-14 shrink-0 flex-col items-center gap-1"
				>
					<ActCell v-if="'act' in cell" :cell="cell" tile />
					<button
						v-else
						type="button"
						:class="[
							TILE,
							cell.key === chosen ? 'bg-surface-gray-4' : 'bg-surface-gray-3',
						]"
						:aria-label="cell.label"
						:aria-current="cell.key === current.railKey ? 'page' : undefined"
						:aria-pressed="cell.key === chosen"
						@click="pick(cell)"
					>
						<Icon v-if="cell.icon" :name="cell.icon" />
						<span v-else class="text-sm font-medium">{{ cell.label.charAt(0) }}</span>
					</button>
					<span class="w-full truncate text-center text-xs text-ink-gray-6">{{
						cell.label
					}}</span>
				</div>
			</nav>

			<nav
				v-if="rows.length"
				class="flex flex-col gap-0.5 px-2 pt-1 [&_.h-7]:h-9 [&_[data-slot=sidebar-item]]:h-9"
				:aria-label="chosenLabel"
				data-phone-rows
			>
				<SidebarRow
					v-for="node in rows"
					:key="`${chosenAddress}:${node.item.key}`"
					:node="node"
					:context="contexts.sidebars[chosenAddress!]"
					:current="current.sidebar === chosenAddress ? current.rowKey : undefined"
					:sections="sections[chosenAddress!]"
					:sidebar="chosenAddress"
				/>
			</nav>
		</div>
	</BottomSheet>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { BottomSheet, MobileNav, MobileNavItem } from "frappe-ui";
import type { NavigationItem } from "@/boot";
import { __ } from "@/i18n";
import Icon from "@/icons/Icon.vue";
import type { CurrentNavigation, NavigationContexts } from "@/navigation/current";
import type { SectionMemory } from "@/navigation/sectionMemory";
import { useItemTree } from "@/navigation/useItemTree";
import { useAppMenu } from "./appMenu";
import { useTabBarInset } from "./navigationInset";
import NavigationHeader from "./NavigationHeader.vue";
import { openPalette } from "./palette";
import ActCell from "./RailActCell.vue";
import { useRailCells, type Cell } from "./railCells";
import SidebarRow from "./SidebarRow.vue";
import { loadDocument } from "./tabKeepAlive";
import UserMenu from "./UserMenu.vue";

const props = defineProps<{
	items: NavigationItem[];
	contexts: NavigationContexts;
	sidebars: Record<string, NavigationItem[]>;
	sections: Record<string, SectionMemory>;
	current: CurrentNavigation;
}>();

const TILE =
	"flex size-9 items-center justify-center rounded-4 text-base text-ink-gray-8 transition focus-visible:ring-0 focus-visible:focus-ring";

const { boot, appTitle } = useAppMenu();
const router = useRouter();
const route = useRoute();

const open = ref(false);

// The page ends above the bar and the floats stand above it: both read its measured height.
const bar = ref<{ $el: HTMLElement } | null>(null);
useTabBarInset(computed(() => bar.value?.$el));
const cells = useRailCells(
	() => props.items,
	() => props.contexts.rail
);

// The tile whose rows show: the current one on each open, then whichever a tap picked.
const chosen = ref<string | undefined>(props.current.railKey);
watch(open, (isOpen) => isOpen && (chosen.value = props.current.railKey));

const chosenCell = computed(() => cells.value.find((cell) => cell.key === chosen.value));
const chosenAddress = computed(() => {
	const address = chosenCell.value && "sidebar" in chosenCell.value && chosenCell.value.sidebar;
	return address && props.sidebars[address]?.length ? address : undefined;
});
const chosenLabel = computed(() => chosenCell.value?.label);
const tree = useItemTree(
	() => (chosenAddress.value ? props.sidebars[chosenAddress.value] : []),
	"the sidebar"
);
const rows = computed(() => (chosenAddress.value ? tree.value : []));

function pick(cell: Cell) {
	if ("sidebar" in cell && cell.sidebar && props.sidebars[cell.sidebar]?.length) {
		chosen.value = cell.key;
		return;
	}
	open.value = false;
	if ("to" in cell) router.push(cell.to);
	else if ("href" in cell && cell.href) {
		if (cell.external) window.open(cell.href, "_blank", "noopener");
		else loadDocument(cell.href);
	}
}

// An act opens a dialog and a link may leave the route as is: close the sheet in both cases.
function closeOnAct(event: MouseEvent) {
	if ((event.target as Element).closest("button[aria-busy], a[href]")) open.value = false;
}

// A row or a tile that navigates closes the sheet.
watch(
	() => route.fullPath,
	() => (open.value = false)
);
</script>
