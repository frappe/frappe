<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Button, TabButtons } from "frappe-ui";
import LucideCheckCheck from "~icons/lucide/check-check";
import LucideX from "~icons/lucide/x";
import NotificationItem from "./NotificationItem.vue";
import type { NotificationLog, NotificationPanelProps, NotificationTab } from "./types";

const props = withDefaults(defineProps<NotificationPanelProps>(), {
	title: "Notifications",
});

const emit = defineEmits<{
	close: [];
}>();

// a tab's stable key — used as the TabButtons value and the `#tab-<value>` slot name
const tabValue = (tab: NotificationTab) => tab.value ?? tab.label;

const activeTab = ref<string | undefined>(props.tabs?.[0] ? tabValue(props.tabs[0]) : undefined);

const currentTab = computed(() => props.tabs?.find((t) => tabValue(t) === activeTab.value));

// rows to render: a tab's function filter is applied client-side here; an object filter is
// pushed to the server via setFilters (see the watch below), so it's already reflected in props.
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

// switch server-side filters when the tab changes (object filter → server; function/none → clear)
watch(activeTab, () => {
	const f = currentTab.value?.filter;
	props.setFilters(f && typeof f !== "function" ? f : {});
});

function selectTab(value: string) {
	activeTab.value = value;
}

function close() {
	emit("close");
}

function onItemClick(n: NotificationLog) {
	// host side-effects (routing) ride useNotifications' afterMarkAsRead hook
	props.markAsRead(n.name);
}

const headerScope = computed(() => ({
	title: props.title,
	unreadCount: props.unreadCount,
	tabs: props.tabs ?? [],
	activeTab: activeTab.value,
	selectTab,
	markAllAsRead: props.markAllAsRead,
	close,
}));

const bodyScope = computed(() => ({
	notifications: visibleNotifications.value,
	markAsRead: props.markAsRead,
	loadMore: props.loadMore,
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
					:icon="LucideCheckCheck"
					size="sm"
					@click="markAllAsRead()"
				/>
				<Button variant="ghost" size="sm" tooltip="Close" :icon="LucideX" @click="close" />
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
						<!-- fully custom row -->
						<div v-if="$slots.item" @click="onItemClick(n)">
							<slot name="item" :notification="n" :mark-as-read="markAsRead" />
						</div>
						<!-- default row -->
						<NotificationItem
							:class="i === visibleNotifications.length - 1 ? '' : 'border-b'"
							v-else
							:notification="n"
							@click="onItemClick"
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
