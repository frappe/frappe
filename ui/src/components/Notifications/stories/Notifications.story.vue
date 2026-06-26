<template>
	<div class="p-6 max-w-xl">
		<!-- ── NotificationPanel playground ────────────────────────────────────
		     The panel is UI only — it renders an injected controller. Here we
		     hand it a *mock* controller (fixture rows + no-op verbs) instead of
		     useNotifications(), so it runs with no backend. This also doubles as
		     the no-UI-regression check: the default panel should look unchanged. -->
		<h3 class="mb-3 text-xl-semibold text-ink-gray-9">NotificationPanel</h3>

		<div class="mb-4 flex flex-wrap items-center gap-4">
			<Switch v-model="withTabs" label="Tabs" />
			<Switch v-model="empty" label="Empty" />
			<Switch v-model="loading" label="Loading" />
			<Switch v-model="errored" label="Error" />
		</div>

		<div class="h-[480px] rounded-lg border border-outline-gray-2 overflow-hidden">
			<NotificationPanel
				v-bind="controller"
				:tabs="withTabs ? tabs : undefined"
				@mark-as-read="(n) => controller.markAsRead(n.name)"
				@mark-all-as-read="controller.markAllAsRead"
				@load-more="controller.loadMore"
				@tab-change="controller.filterByTab"
				@close="onClose"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { Switch } from "frappe-ui";
import NotificationPanel from "../NotificationPanel.vue";
import type { NotificationLog, NotificationStore, NotificationTab } from "../types";

const withTabs = ref(false);
const empty = ref(false);
const loading = ref(false);
const errored = ref(false);

const fixtures: NotificationLog[] = [
	{
		name: "1",
		title: "<b>Jane Doe</b> assigned you a task",
		description: "Follow up with the customer about the renewal",
		from_user: "jane@example.com",
		read: 0,
		creation: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
	},
	{
		name: "2",
		title: "<b>Acme Corp</b> deal moved to Negotiation",
		description: "Stage changed by John",
		type: "Alert",
		read: 1,
		creation: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
	},
	{
		name: "3",
		title: "System backup completed",
		read: 1,
		creation: new Date(Date.now() - 26 * 60 * 60 * 1000).toISOString(),
	},
];

const tabs: NotificationTab[] = [
	{ label: "All" },
	{ label: "Unread", value: "unread", filter: (n) => !n.read, count: "unread" },
	{ label: "Alerts", value: "alerts", filter: { type: "Alert" } },
];

// the empty / loading / error states only render when there are no rows, so each toggle
// clears the feed to show its branch
const hasRows = computed(() => !empty.value && !loading.value && !errored.value);

// a mock of the useNotifications() controller — fixture data + no-op verbs
const controller = reactive({
	notifications: computed<NotificationLog[]>(() => (hasRows.value ? fixtures : [])),
	unreadCount: computed(() => (hasRows.value ? fixtures.filter((n) => !n.read).length : 0)),
	hasNextPage: false,
	loading: computed(() => loading.value),
	error: computed(() => (errored.value ? new Error("Network error") : null)),
	markAsRead: async (name: string) => console.log("markAsRead", name),
	markAllAsRead: async () => console.log("markAllAsRead"),
	markSeen: () => console.log("markSeen"),
	reload: () => console.log("reload"),
	loadMore: () => console.log("loadMore"),
	setFilters: (f: Record<string, unknown>) => console.log("setFilters", f),
	filterByTab: (tab?: NotificationTab) => console.log("filterByTab", tab?.label),
}) as NotificationStore;

function onClose() {
	console.log("close");
}
</script>
