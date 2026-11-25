<script setup lang="ts">
import { computed, watch } from "vue";
import { Avatar, Button, Icon, TabButtons, dayjs } from "frappe-ui";
import { List, ListCell, ListRow } from "frappe-ui/list";
import { translate as __ } from "../utils/translate";
import type { NotificationLog, NotificationTab } from "../components/Notifications/types";
import type { NotificationsProps } from "./types";

// `v-bind="useNotifications()"` also passes the store's functions, which are not props
defineOptions({ inheritAttrs: false });

const props = withDefaults(defineProps<NotificationsProps>(), {
	tabs: () => [
		{ label: __("Unread"), value: "unread", filter: (n: NotificationLog) => !n.read },
		{ label: __("Read"), value: "read", filter: (n: NotificationLog) => Boolean(n.read) },
	],
});

const emit = defineEmits<{
	select: [notification: NotificationLog];
	"mark-as-read": [notification: NotificationLog];
	"mark-all-as-read": [];
	"load-more": [];
	"tab-change": [tab: NotificationTab | undefined];
}>();

const activeTab = defineModel<string | undefined>("activeTab");

const tabValue = (tab: NotificationTab) => tab.value ?? tab.label;

if (activeTab.value === undefined && props.tabs.length) {
	activeTab.value = tabValue(props.tabs[0]);
}

const currentTab = computed(() => props.tabs.find((tab) => tabValue(tab) === activeTab.value));

// A tab's function filter runs here. An object filter is the host's to apply on `tab-change`.
const visible = computed(() => {
	const filter = currentTab.value?.filter;
	return typeof filter === "function" ? props.notifications.filter(filter) : props.notifications;
});

const hasUnread = computed(() => visible.value.some((n) => !n.read));

function tabCount(tab: NotificationTab) {
	if (tab.count === "unread") return props.unreadCount;
	if (typeof tab.count === "function") return tab.count(props.notifications);
	return undefined;
}

const tabButtons = computed(() =>
	props.tabs.map((tab) => {
		const count = tabCount(tab);
		return { label: count ? `${tab.label} (${count})` : tab.label, value: tabValue(tab) };
	})
);

watch(activeTab, () => emit("tab-change", currentTab.value));

const message = (n: NotificationLog) => n.title || n.subject || "";

const target = (n: NotificationLog) =>
	n.document_type ? `${__(n.document_type)} ${n.document_name || ""}` : "";

// Written out whole, so Tailwind's scan finds every icon class.
const ICONS: Record<string, string> = {
	Mention: "lucide-at-sign",
	Assignment: "lucide-user-check",
	Share: "lucide-share-2",
	"Energy Point": "lucide-zap",
	Alert: "lucide-bell",
};
</script>

<template>
	<div data-slot="notifications" class="h-full overflow-y-auto pt-4 pb-10">
		<slot
			name="header"
			:tabs="tabs"
			:active-tab="activeTab"
			:unread-count="unreadCount"
			:mark-all-as-read="() => emit('mark-all-as-read')"
		>
			<div
				data-slot="notifications-header"
				class="mb-3 flex items-center justify-between gap-3 px-4"
			>
				<TabButtons v-if="tabs.length" v-model="activeTab" :options="tabButtons" />
				<Button v-if="hasUnread" @click="emit('mark-all-as-read')">
					{{ __("Mark all as read") }}
				</Button>
			</div>
		</slot>

		<slot v-if="loading && !notifications.length" name="loading">
			<div data-slot="notifications-loading" class="space-y-3 px-4" aria-busy="true">
				<span class="sr-only">{{ __("Loading...") }}</span>
				<div v-for="index in 3" :key="index" class="flex h-[68px] items-center gap-3">
					<div class="size-10 shrink-0 animate-pulse rounded-full bg-surface-gray-2" />
					<div class="flex-1 space-y-2">
						<div class="h-3 w-3/4 animate-pulse rounded bg-surface-gray-2" />
						<div class="h-3 w-1/3 animate-pulse rounded bg-surface-gray-2" />
					</div>
				</div>
			</div>
		</slot>

		<template v-else-if="visible.length">
			<!-- the message is the backend's own markup: a <b> around the document title -->
			<List class="list-gap-3 list-row-px-4 pr-3 [&_b]:font-medium [&_b]:text-ink-gray-9">
				<ListRow
					v-for="(item, index) in visible"
					:key="item.name"
					:data-unread="item.read ? undefined : ''"
					class="group h-[68px]"
					:class="!item.read && 'w-[calc(100%-2.5rem)]'"
					@click="emit('select', item)"
				>
					<ListCell>
						<slot name="item-prefix" :item="item" :index="index">
							<Avatar
								v-if="item.from_user"
								size="2xl"
								:image="item.from_user_image"
								:label="item.from_user"
							/>
							<div
								v-else
								class="grid size-10 place-items-center rounded-4 bg-surface-gray-2"
							>
								<Icon
									:name="ICONS[item.type || ''] || 'lucide-bell'"
									class="size-5 text-ink-gray-6"
								/>
							</div>
						</slot>
					</ListCell>
					<ListCell>
						<div class="min-w-0 flex-1">
							<slot name="item-label" :item="item" :index="index">
								<!-- sanitized by the backend when the log is written -->
								<p
									class="truncate leading-none text-ink-gray-8"
									:class="item.read ? 'text-lg' : 'text-lg-medium'"
									v-html="message(item)"
								/>
								<p
									v-if="target(item)"
									class="mt-1.5 truncate text-md text-ink-gray-5"
								>
									{{ target(item) }}
								</p>
							</slot>
						</div>
					</ListCell>
					<ListCell class="justify-end">
						<slot name="item-suffix" :item="item" :index="index">
							<time
								class="block shrink-0 whitespace-nowrap text-right text-sm text-ink-gray-5"
								:datetime="item.creation"
							>
								{{ dayjs(item.creation).fromNow() }}
							</time>
						</slot>
					</ListCell>
					<!-- Sits in the 2.5rem gutter the unread row's reduced width leaves free.
					     stop+prevent keep the click from bubbling into the row. -->
					<div
						v-if="!item.read"
						class="absolute -right-10 top-1/2 z-10 -translate-y-1/2"
					>
						<Button
							variant="subtle"
							icon="lucide-check"
							:aria-label="__('Mark as read')"
							@click.stop.prevent="emit('mark-as-read', item)"
						/>
					</div>
				</ListRow>
			</List>

			<div v-if="hasNextPage" class="p-3 text-center">
				<Button :label="__('Load more')" @click="emit('load-more')" />
			</div>
		</template>

		<slot v-else-if="error" name="error" :error="error">
			<p data-slot="notifications-error" class="py-14 text-center text-base text-ink-gray-6">
				{{ __("Couldn't load notifications") }}
			</p>
		</slot>

		<slot v-else name="empty" :active-tab="activeTab">
			<div
				data-slot="notifications-empty"
				class="mx-4 rounded-4 border border-dashed border-outline-gray-2 px-6 py-12 text-center"
			>
				<div class="mx-auto grid size-10 place-items-center rounded-4 bg-surface-gray-2">
					<span class="lucide-bell-check size-5 text-ink-gray-5" aria-hidden="true" />
				</div>
				<div class="mt-3 text-base-medium text-ink-gray-8">
					{{
						activeTab === "unread"
							? __("You're caught up")
							: activeTab === "read"
							? __("No read notifications")
							: __("No notifications to show")
					}}
				</div>
				<div v-if="activeTab === 'unread'" class="mt-1 text-base text-ink-gray-5">
					{{ __("New notifications will show up here.") }}
				</div>
				<div v-else-if="activeTab === 'read'" class="mt-1 text-base text-ink-gray-5">
					{{ __("Notifications you have read collect here.") }}
				</div>
			</div>
		</slot>
	</div>
</template>
