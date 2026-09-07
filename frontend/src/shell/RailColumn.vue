<!--
  The rail on frappe-ui's `Rail`: an icon column with the app tile first, which opens the app menu.
  A heading has no icon form, so its children draw flat; rows fetched on demand are not drawn.
-->
<template>
	<Rail>
		<div class="mb-3 flex shrink-0 items-center justify-center">
			<!-- A raw button: `Dropdown` cannot reach a trigger through `RailItem`'s `Tooltip`. -->
			<Dropdown :options="menu" side="right" align="start">
				<button
					type="button"
					data-key="app-menu"
					:class="[TILE, boot.app_logo ? 'hover:opacity-90' : LETTER_TILE]"
					:aria-label="`${appTitle} menu`"
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

		<nav
			class="flex w-full flex-1 flex-col items-center gap-3 overflow-y-auto"
			:aria-label="appTitle"
		>
			<!-- `RailItem`'s `Tooltip` drops attributes, so the test hooks sit on a wrapper. -->
			<div
				v-for="cell in cells"
				:key="cell.key"
				:data-key="cell.key"
				:data-sidebar="cell.sidebar"
			>
				<RailItem
					v-if="'to' in cell"
					:to="cell.to"
					:label="cell.label"
					:active="cell.key === current"
				>
					<Icon v-if="cell.icon" :name="cell.icon" />
					<span v-else class="text-sm font-medium">{{ cell.label.charAt(0) }}</span>
				</RailItem>

				<!-- Off this prefix: a full document load. `RailItem` has no anchor form, so a button. -->
				<RailItem
					v-else
					:label="cell.label"
					:active="cell.key === current"
					@click="leave(cell.href)"
				>
					<Icon v-if="cell.icon" :name="cell.icon" />
					<span v-else class="text-sm font-medium">{{ cell.label.charAt(0) }}</span>
				</RailItem>
			</div>
		</nav>
	</Rail>
</template>

<script setup lang="ts">
import { computed, inject } from "vue";
import type { RouteLocationRaw } from "vue-router";
import { Dropdown, Rail, RailItem, toast, useColorScheme, type DropdownOptions } from "frappe-ui";
import type { Boot, NavigationItem } from "@/boot";
import Icon from "@/icons/Icon.vue";
import { labelOf, renderingOf } from "@/navigation/registry";
import type { ItemNode } from "@/navigation/tree";
import { useItemTree } from "@/navigation/useItemTree";
import type { ItemContext } from "@/navigation/types";

type Cell = { key: string; label: string; icon?: string; sidebar?: string } & (
	| { to: RouteLocationRaw }
	| { href: string }
);

const TILE =
	"flex size-7 items-center justify-center rounded-[7px] transition focus-visible:ring-0 focus-visible:focus-ring";
const LETTER_TILE =
	"bg-surface-gray-3 text-sm font-medium text-ink-gray-8 hover:bg-surface-gray-4";

// The shell decides `arrangeable` (off on the index), `current` (one row across rail and panel)
// and `shareLink` (it knows whether the panel needs naming); a context is composed once per list.
const props = defineProps<{
	items: NavigationItem[];
	context: ItemContext;
	current?: string;
	arrangeable?: boolean;
	shareLink?: string;
}>();
const emit = defineEmits<{ arrange: [] }>();

const boot = inject<Boot>("boot")!;

const appTitle = computed(() => boot.app_title ?? boot.app ?? "Apps");

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

const { colorScheme, setColorScheme } = useColorScheme();
const SCHEMES = [
	{ label: "Light", value: "light", icon: "lucide-sun" },
	{ label: "Dark", value: "dark", icon: "lucide-moon" },
	{ label: "System", value: "system", icon: "lucide-monitor" },
] as const;

const menu = computed<DropdownOptions>(() => [
	{ label: "All apps", icon: "lucide-layout-grid", onClick: () => leave("/apps") },
	{
		label: "Theme",
		icon: "lucide-sun-moon",
		submenu: SCHEMES.map((scheme) => ({
			label: scheme.label,
			icon: scheme.icon,
			selected: colorScheme.value === scheme.value,
			onClick: () => setColorScheme(scheme.value),
		})),
	},
	...(props.arrangeable
		? [
				{
					label: "Customize sidebar",
					icon: "lucide-settings-2",
					onClick: () => emit("arrange"),
				},
		  ]
		: []),
	...(props.shareLink ? [{ label: "Copy link", icon: "lucide-link", onClick: copyLink }] : []),
]);

function leave(href: string) {
	window.location.assign(href);
}

// The menu closes on the click, so the confirmation is a toast.
async function copyLink() {
	if (!props.shareLink) return;
	try {
		await navigator.clipboard.writeText(props.shareLink);
	} catch {
		toast.error("Could not copy the link");
		return;
	}
	toast.success("Link copied");
}
</script>
