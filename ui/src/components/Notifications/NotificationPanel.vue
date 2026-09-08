<script setup lang="ts">
import { computed, watch } from "vue";
import { Button, TabButtons } from "frappe-ui";
import LucideCheckCheck from "~icons/lucide/check-check";
import LucideX from "~icons/lucide/x";
import NotificationItem from "./NotificationItem.vue";
import type { NotificationLog, NotificationPanelProps, NotificationTab } from "./types";

// data binds as props (v-bind="controller"); the controller's verb members fall through as
// attrs, so don't inherit them onto the root — actions are surfaced as events instead.
defineOptions({ inheritAttrs: false });

const props = withDefaults(defineProps<NotificationPanelProps>(), {
	title: "Notifications",
});

const emit = defineEmits<{
	close: [];
	"mark-as-read": [n: NotificationLog];
	"mark-all-as-read": [];
	"load-more": [];
	"tab-change": [tab: NotificationTab | undefined];
}>();

// controllable active tab (P2); falls back to the first tab when uncontrolled
const activeTab = defineModel<string | undefined>("activeTab");

// a tab's stable key — used as the TabButtons value and the `#tab-<value>` slot name
const tabValue = (tab: NotificationTab) => tab.value ?? tab.label;

if (activeTab.value === undefined && props.tabs?.length) {
	activeTab.value = tabValue(props.tabs[0]);
}

const currentTab = computed(() => props.tabs?.find((t) => tabValue(t) === activeTab.value));

// rows to render: a tab's function filter is applied client-side here; an object filter is
// applied by the host on `tab-change` (it re-queries the server), so props already reflect it.
const visibleNotifications = computed<NotificationLog[]>(() => {
	const f = currentTab.value?.filter;
	return typeof f === "function" ? props.notifications.filter(f) : props.notifications;
});

function tabCount(tab: NotificationTab) {
	if (tab.count === "unread") return props.unreadCount;
	if (typeof tab.count === "function") return tab.count(props.notifications);
	return undefined;
}

// buttons for the frappe-ui TabButtons segmented control. TabButtons has no per-button badge
// slot, so a non-zero count is surfaced inline in the label.
const tabButtons = computed(() =>
	(props.tabs ?? []).map((tab) => {
		const count = tabCount(tab);
		return {
			label: count ? `${tab.label} (${count})` : tab.label,
			value: tabValue(tab),
		};
	})
);

// announce the active tab when it changes; the host applies its filter (e.g. via the
// controller's filterByTab). Function filters are applied client-side in visibleNotifications.
watch(activeTab, () => emit("tab-change", currentTab.value));

function selectTab(value: string) {
	activeTab.value = value;
}
function close() {
	emit("close");
}
function markAllAsRead() {
	emit("mark-all-as-read");
}
function markRead(n: NotificationLog) {
	emit("mark-as-read", n);
}
function loadMore() {
	emit("load-more");
}

const headerScope = computed(() => ({
	title: props.title,
	unreadCount: props.unreadCount,
	tabs: props.tabs ?? [],
	activeTab: activeTab.value,
	selectTab,
	markAllAsRead,
	close,
}));

const bodyScope = computed(() => ({
	notifications: visibleNotifications.value,
	markAsRead: markRead,
	loadMore,
	hasNextPage: props.hasNextPage,
}));

// per-tab body override, e.g. <template #tab-unread>
const activeTabSlot = computed(() => (activeTab.value ? `tab-${activeTab.value}` : undefined));
</script>

<template>
	<div class="flex flex-col bg-surface-base text-ink-gray-9 w-full h-full">
		<!-- header -->
		<slot name="header" v-bind="headerScope">
			<div class="flex items-center gap-2 px-4 py-2 pt-4">
				<span class="text-md font-medium mr-auto">{{ title }}</span>
				<Button
					variant="ghost"
					tooltip="Mark all as read"
					aria-label="Mark all as read"
					:icon="LucideCheckCheck"
					size="sm"
					@click="markAllAsRead"
				/>
				<Button
					variant="ghost"
					size="sm"
					tooltip="Close"
					aria-label="Close"
					:icon="LucideX"
					@click="close"
				/>
			</div>
		</slot>

		<!-- tabs -->
		<TabButtons
			v-if="tabs?.length"
			v-model="activeTab"
			:options="tabButtons"
			class="px-4 py-2 [&>div]:w-full [&_button]:flex-1 [&_button>*]:w-full"
		/>

		<!-- body -->
		<div class="flex-1 overflow-y-auto">
			<!-- per-tab body override -->
			<slot
				v-if="activeTabSlot && $slots[activeTabSlot]"
				:name="activeTabSlot"
				v-bind="bodyScope"
			/>
			<!-- whole-body override -->
			<slot v-else-if="$slots.default" v-bind="bodyScope" />
			<!-- default body -->
			<template v-else>
				<template v-if="visibleNotifications.length">
					<template v-for="(n, i) in visibleNotifications" :key="n.name">
						<!-- fully custom row (consumer owns interaction; calls markAsRead) -->
						<slot
							v-if="$slots.item"
							name="item"
							:notification="n"
							:mark-as-read="markRead"
						/>
						<!-- default row -->
						<NotificationItem
							v-else
							:class="i === visibleNotifications.length - 1 ? '' : 'border-b'"
							:notification="n"
							@click="markRead"
						/>
					</template>

					<div v-if="hasNextPage" class="p-3 text-center">
						<Button label="Load more" size="sm" @click="loadMore" />
					</div>
				</template>

				<!-- error state (renders only on fetch failure; nothing shows while healthy) -->
				<slot v-else-if="error" name="error" :error="error">
					<div class="py-12 text-center text-p-sm text-ink-gray-5">
						Couldn't load notifications
					</div>
				</slot>

				<!-- only show the empty state once a load has settled, so a cold first fetch doesn't
				     flash "No notifications" before rows arrive (reopens render cached rows instantly) -->
				<slot v-else-if="!loading" name="empty">
					<div class="py-12 text-center text-p-sm text-ink-gray-5">
						No notifications to show
					</div>
				</slot>
			</template>
		</div>
	</div>
</template>
