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

		<!-- Stretched over `SidebarRail`'s own padding, so the scrollbar sits on the rail's edge. -->
		<ScrollArea class="-mx-[11px] min-h-0 flex-1 self-stretch" viewportClass="px-[11px]">
			<nav class="flex flex-col items-center gap-3" :aria-label="appTitle">
				<!-- `SidebarRailItem`'s `Tooltip` drops attributes, so the test hooks sit on a wrapper. -->
				<div
					v-for="cell in cells"
					:key="cell.key"
					:data-key="cell.key"
					:data-sidebar="cell.sidebar"
				>
					<SidebarRailItem
						v-if="'to' in cell"
						:to="cell.to"
						:label="cell.label"
						:active="cell.key === current"
					>
						<Icon v-if="cell.icon" :name="cell.icon" />
						<span v-else class="text-sm font-medium">{{ cell.label.charAt(0) }}</span>
					</SidebarRailItem>

					<!-- Off this prefix: a full document load, so an `<a>` with `SidebarRailItem`'s classes,
					     which has no anchor form of its own. Never current: `current` is a route. -->
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
			<Dropdown :options="userMenu" side="right" align="end">
				<button
					type="button"
					data-key="user-menu"
					:class="USER_CELL"
					:aria-label="boot.user.full_name"
				>
					<Avatar :image="boot.user.user_image" :label="boot.user.full_name" size="lg" />
				</button>
			</Dropdown>
		</div>

		<LogoutDialog v-model="confirmingLogout" />
	</SidebarRail>
</template>

<script setup lang="ts">
import { computed, h, inject, ref } from "vue";
import type { RouteLocationRaw } from "vue-router";
import {
	Avatar,
	Dropdown,
	SidebarRail,
	SidebarRailItem,
	ScrollArea,
	Tooltip,
	toast,
	useColorScheme,
	type DropdownOptions,
} from "frappe-ui";
import type { Boot, NavigationItem } from "@/boot";
import Icon from "@/icons/Icon.vue";
import { labelOf, renderingOf } from "@/navigation/registry";
import type { ItemNode } from "@/navigation/tree";
import { useItemTree } from "@/navigation/useItemTree";
import type { ItemContext } from "@/navigation/types";
import LogoutDialog from "./LogoutDialog.vue";

type Cell = { key: string; label: string; icon?: string; sidebar?: string } & (
	| { to: RouteLocationRaw }
	| { href: string }
);

const TILE =
	"flex size-7 items-center justify-center rounded-[7px] transition focus-visible:ring-0 focus-visible:focus-ring";
const LETTER_TILE =
	"bg-surface-gray-3 text-sm font-medium text-ink-gray-8 hover:bg-surface-gray-4";
const USER_CELL =
	"flex rounded-full transition hover:opacity-90 focus-visible:ring-0 focus-visible:focus-ring";
// `SidebarRailItem`'s own inactive tile.
const CELL =
	"relative flex size-7 shrink-0 items-center justify-center rounded-[7px] bg-surface-gray-3 text-base transition focus-visible:ring-0 focus-visible:focus-ring";

// The shell decides `customizable` (off on the index), `current` (one row across rail and panel)
// and `shareLink` (it knows whether the panel needs naming); a context is composed once per list.
const props = defineProps<{
	items: NavigationItem[];
	context: ItemContext;
	current?: string;
	customizable?: boolean;
	shareLink?: string;
}>();
const emit = defineEmits<{ customize: [] }>();

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

const menu = computed<DropdownOptions>(() => [
	{ label: "All apps", icon: "lucide-layout-grid", onClick: () => leave("/apps") },
	...(props.customizable
		? [
				{
					label: "Customize sidebar",
					icon: "lucide-settings-2",
					onClick: () => emit("customize"),
				},
		  ]
		: []),
	...(props.shareLink ? [{ label: "Copy link", icon: "lucide-link", onClick: copyLink }] : []),
]);

const { colorScheme, setColorScheme } = useColorScheme();
const SCHEMES = [
	{ label: "Light", value: "light", icon: "lucide-sun" },
	{ label: "Dark", value: "dark", icon: "lucide-moon" },
	{ label: "System", value: "system", icon: "lucide-monitor" },
] as const;

const confirmingLogout = ref(false);

// Workaround: the settings dialog has no profile pane yet, so *My settings* opens v1's User form.
const userMenu = computed<DropdownOptions>(() => [
	{ group: "", hideLabel: true, options: [profileHeader()] },
	{
		group: "",
		hideLabel: true,
		options: [
			{
				label: "My settings",
				icon: "lucide-circle-user",
				onClick: () => leave(`/app/user/${encodeURIComponent(boot.user.name)}`),
			},
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
		],
	},
	{
		group: "",
		hideLabel: true,
		options: [
			{ label: "Desk v1", icon: "lucide-arrow-left-right", onClick: () => leave("/app") },
		],
	},
	{
		group: "",
		hideLabel: true,
		options: [
			{
				label: "Log out",
				icon: "lucide-log-out",
				theme: "red",
				onClick: () => (confirmingLogout.value = true),
			},
		],
	},
]);

// A disabled row cannot be selected; the inline cursor beats the wrapper's `cursor-not-allowed`.
function profileHeader() {
	const { full_name, user_image, email } = boot.user;
	return {
		label: full_name,
		disabled: true,
		slots: {
			item: () =>
				h(
					"div",
					{
						"data-key": "profile",
						class: "flex items-center gap-1.5 px-2 py-1.5",
						style: { cursor: "default" },
					},
					[
						h(Avatar, { image: user_image, label: full_name, size: "xl" }),
						h("div", { class: "flex flex-col gap-0.5 min-w-0" }, [
							h(
								"div",
								{ class: "truncate text-sm font-semibold text-ink-gray-9" },
								full_name
							),
							h("div", { class: "truncate text-xs text-ink-gray-5" }, email),
						]),
					]
				),
		},
	};
}

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
