<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { Avatar } from "frappe-ui";
import { Notifications } from "@framework/ui/mobile";
import { on_phone_visit } from "../search/phone_page.js";

// Gameplan's notifications page, drawn from desk's Notification Log.

const props = defineProps({
	route: { type: Array, default: () => [] },
	query: { type: Object, default: () => ({}) },
});

const emit = defineEmits(["title", "actions"]);

const frappe = window.frappe;
const __ = window.__;

// The sidebar's notifications view (frappe.ui.Notifications): this page links and counts
// through it, so the page, the panel and the unread badge agree.
const view = frappe.app.sidebar?.notifications?.tabs?.notifications;

const LIMIT = 100;
const GET_LOGS = "frappe.desk.doctype.notification_log.notification_log.get_notification_logs";
const MARK_AS_READ = "frappe.desk.doctype.notification_log.notification_log.mark_as_read";
const MARK_ALL_AS_READ = "frappe.desk.doctype.notification_log.notification_log.mark_all_as_read";

const logs = ref([]);
const loading = ref(true);
const active_tab = ref("unread");
const unread_count = computed(() => logs.value.filter((log) => !log.read).length);

function load() {
	if (!view) {
		loading.value = false;
		return;
	}
	// unread and read apart, so a run of newer read logs cannot push older unread ones out
	Promise.all([0, 1].map((read) => frappe.xcall(GET_LOGS, { limit: LIMIT, read }))).then(
		(pages) => {
			pages.forEach((page) => frappe.update_user_info(page.user_info));
			logs.value = pages.flatMap((page) => page.notification_logs);
			loading.value = false;
		}
	);
}

// the badge moves by what was marked, as in the panel: the page holds at most LIMIT unread logs
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

onMounted(() => frappe.realtime.on("notification", load));
onUnmounted(() => frappe.realtime.off("notification", load));

on_phone_visit(props, ["List", "Notification Log"], () => {
	emit("title", __("Notifications"));
	emit("actions", []);
	load();
});

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
	<Notifications
		v-model:active-tab="active_tab"
		:notifications="logs"
		:unread-count="unread_count"
		:loading="loading"
		@select="open"
		@mark-as-read="mark_as_read"
		@mark-all-as-read="mark_all_as_read"
	>
		<template #item-prefix="{ item }">
			<Avatar
				v-if="item.from_user"
				size="2xl"
				:image="user(item).image"
				:label="user(item).fullname"
			/>
			<div v-else class="grid size-10 place-items-center rounded-4 bg-surface-gray-2">
				<span
					:class="[ICONS[item.type] || 'lucide-bell', 'size-5 text-ink-gray-6']"
					aria-hidden="true"
				/>
			</div>
		</template>

		<template #item-suffix="{ item }">
			<time
				class="block shrink-0 whitespace-nowrap text-right text-sm text-ink-gray-5"
				:datetime="item.creation"
			>
				{{ frappe.datetime.prettyDate(item.creation, true) }}
			</time>
		</template>

		<template v-if="!view" #empty>
			<div
				class="mx-4 rounded-4 border border-dashed border-outline-gray-2 px-6 py-12 text-center"
			>
				<div class="mx-auto grid size-10 place-items-center rounded-4 bg-surface-gray-2">
					<span class="lucide-bell-check size-5 text-ink-gray-5" aria-hidden="true" />
				</div>
				<div class="mt-3 text-base-medium text-ink-gray-8">
					{{ __("Notifications are turned off for you") }}
				</div>
			</div>
		</template>
	</Notifications>
</template>
