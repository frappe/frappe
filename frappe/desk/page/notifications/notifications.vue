<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { Avatar, Button, TabButtons } from "frappe-ui";
import { List, ListCell, ListRow } from "frappe-ui/list";

// Gameplan's notifications page, drawn from desk's Notification Log.

defineProps({
	route: { type: Array, default: () => [] },
	query: { type: Object, default: () => ({}) },
});

const emit = defineEmits(["title", "actions"]);

const frappe = window.frappe;
const __ = window.__;

// The sidebar's notifications view (frappe.ui.Notifications): this page fetches, links and
// counts through it, so the page, the panel and the unread badge agree.
const view = frappe.app.sidebar?.notifications?.tabs?.notifications;

const LIMIT = 100;
const MARK_AS_READ = "frappe.desk.doctype.notification_log.notification_log.mark_as_read";
const MARK_ALL_AS_READ = "frappe.desk.doctype.notification_log.notification_log.mark_all_as_read";

const logs = ref([]);
const loading = ref(true);
const active_tab = ref("Unread");

const tab_options = [
	{ value: "Unread", label: __("Unread") },
	{ value: "Read", label: __("Read") },
];

const notifications = computed(() =>
	logs.value.filter((log) => Boolean(log.read) === (active_tab.value === "Read"))
);
const unread_count = computed(() => logs.value.filter((log) => !log.read).length);

function load() {
	if (!view) {
		loading.value = false;
		return;
	}
	view.get_notifications_list(LIMIT).then((r) => {
		frappe.update_user_info(r.message?.user_info);
		// A System Manager may read everyone's logs, but marking only touches their own,
		// and the badge counts only their own.
		logs.value = (r.message?.notification_logs || []).filter(
			(log) => log.for_user === frappe.session.user
		);
		loading.value = false;
	});
}

// the badge moves by what was marked, as in the panel: the page holds at most LIMIT logs
function mark_as_read(log) {
	log.read = 1;
	view.update_count_badge(Math.max(view.unread_count - 1, 0));
	frappe.call(MARK_AS_READ, { docname: log.name }).catch(() => {
		log.read = 0;
		view.update_count_badge(view.unread_count + 1);
	});
}

function mark_all_as_read() {
	frappe.confirm(__("Mark every notification as read?"), () =>
		frappe.call(MARK_ALL_AS_READ).then(() => {
			logs.value.forEach((log) => (log.read = 1));
			view.update_count_badge(0);
		})
	);
}

function open(log) {
	if (!log.read) mark_as_read(log);
	const link = view.get_item_link(log);
	if (link.startsWith("/desk")) frappe.set_route(link);
	else window.location.href = link;
}

// a new one arrives while the page is open
onMounted(() => frappe.realtime.on("notification", load));
onUnmounted(() => frappe.realtime.off("notification", load));

onMounted(() => {
	// A phone's page. A wider screen has the panel, and the full log the panel links to, so
	// it goes there instead. The route is replaced so Back does not land here again.
	if (!frappe.is_mobile()) {
		frappe.route_flags.replace_route = true;
		frappe.set_route("List", "Notification Log");
		return;
	}

	emit("title", __("Notifications"));
	emit("actions", []);
	load();
});

// Title and Description are the canonical fields; subject is the legacy one. It is desk's own
// markup (a <b> around the document title), rendered as the panel renders it.
function message(log) {
	return log.title || log.subject || "";
}

function target(log) {
	return log.document_type ? `${__(log.document_type)} ${log.document_name || ""}` : "";
}

function user(log) {
	return frappe.user_info(log.from_user);
}

// Written out whole, so Tailwind's scan finds every icon class.
const ICONS = {
	Mention: "lucide-at-sign",
	Assignment: "lucide-user-check",
	Share: "lucide-share-2",
	"Energy Point": "lucide-zap",
	Alert: "lucide-bell",
};
</script>

<template>
	<div class="h-full overflow-y-auto pt-4 pb-10">
		<div class="mb-3 flex items-center justify-between gap-3 px-4">
			<TabButtons v-model="active_tab" :options="tab_options" />
			<Button v-if="active_tab === 'Unread' && unread_count" @click="mark_all_as_read">
				{{ __("Mark all as read") }}
			</Button>
		</div>

		<div v-if="loading" class="space-y-3 px-4">
			<div v-for="index in 3" :key="index" class="flex h-[68px] items-center gap-3">
				<div class="size-10 shrink-0 animate-pulse rounded-full bg-surface-gray-2" />
				<div class="flex-1 space-y-2">
					<div class="h-3 w-3/4 animate-pulse rounded bg-surface-gray-2" />
					<div class="h-3 w-1/3 animate-pulse rounded bg-surface-gray-2" />
				</div>
			</div>
		</div>

		<!-- the message is desk's own markup: a <b> around the document title -->
		<List
			v-else-if="notifications.length"
			class="list-gap-3 list-row-px-4 pr-3 [&_b]:font-medium [&_b]:text-ink-gray-9"
		>
			<ListRow
				v-for="log in notifications"
				:key="log.name"
				class="group h-[68px]"
				:class="!log.read && 'w-[calc(100%-2.5rem)]'"
				@click="open(log)"
			>
				<ListCell>
					<Avatar
						v-if="log.from_user"
						size="2xl"
						:image="user(log).image"
						:label="user(log).fullname"
					/>
					<div
						v-else
						class="grid size-10 place-items-center rounded-[8px] bg-surface-gray-2"
					>
						<span
							:class="[ICONS[log.type] || 'lucide-bell', 'size-5 text-ink-gray-6']"
							aria-hidden="true"
						/>
					</div>
				</ListCell>
				<ListCell>
					<div class="min-w-0 flex-1">
						<p
							class="truncate leading-none text-ink-gray-8"
							:class="log.read ? 'text-lg' : 'text-lg-medium'"
							v-html="message(log)"
						/>
						<p v-if="target(log)" class="mt-1.5 truncate text-md text-ink-gray-5">
							{{ target(log) }}
						</p>
					</div>
				</ListCell>
				<ListCell class="justify-end">
					<time
						class="block shrink-0 whitespace-nowrap text-right text-sm text-ink-gray-5"
						:datetime="log.creation"
					>
						{{ frappe.datetime.prettyDate(log.creation, true) }}
					</time>
				</ListCell>
				<!-- Sits in the 2.5rem gutter the unread row's reduced width leaves free.
				     stop+prevent keep the click from bubbling into the row. -->
				<div v-if="!log.read" class="absolute -right-10 top-1/2 z-10 -translate-y-1/2">
					<Button
						variant="subtle"
						icon="lucide-check"
						:aria-label="__('Mark as read')"
						@click.stop.prevent="mark_as_read(log)"
					/>
				</div>
			</ListRow>
		</List>

		<div
			v-else
			class="mx-4 rounded-4 border border-dashed border-outline-gray-2 px-6 py-12 text-center"
		>
			<div class="mx-auto grid size-10 place-items-center rounded-4 bg-surface-gray-2">
				<span class="lucide-bell-check size-5 text-ink-gray-5" aria-hidden="true" />
			</div>
			<div class="mt-3 text-base-medium text-ink-gray-8">
				{{
					!view
						? __("Notifications are turned off for you")
						: active_tab === "Unread"
						? __("You're caught up")
						: __("No read notifications")
				}}
			</div>
			<div v-if="view" class="mt-1 text-base text-ink-gray-5">
				{{
					active_tab === "Unread"
						? __("New notifications will show up here.")
						: __("Notifications you have read collect here.")
				}}
			</div>
		</div>
	</div>
</template>
