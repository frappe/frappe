<template>
	<div class="p-6 max-w-2xl">
		<!-- ── ActivityTimeline playground ──────────────────────────────────────
		     ActivityTimeline is UI only — it renders an `Activity[]` a host feeds
		     it. Here we hand it *fixtures* (one of each activity type) and a mock
		     `paginate` controller instead of useActivityTimeline(), so it runs with
		     no backend. Toggles exercise the loading / empty / pagination branches
		     and the item `#actions` + custom-type slots. -->
		<h3 class="mb-3 text-xl-semibold text-ink-gray-9">ActivityTimeline</h3>

		<div class="mb-4 flex flex-wrap items-center gap-4">
			<Switch v-model="loading" label="Loading" />
			<Switch v-model="empty" label="Empty" />
			<Switch v-model="paginated" label="Pagination" />
			<Switch v-model="withSlots" label="Slots" />
		</div>

		<div class="rounded-lg border border-outline-gray-2 p-4">
			<ActivityTimeline
				:activities="activities"
				:loading="loading"
				:paginate="paginated ? paginate : undefined"
			>
				<!-- reuse the built-in email/comment rows, adding an #actions region -->
				<template #item-email="{ activity }">
					<EmailItem :email="activity">
						<template v-if="withSlots" #actions>
							<Button variant="ghost" @click="log('reply', activity.data.name)">
								<template #icon
									><LucideReply class="size-4 text-ink-gray-7"
								/></template>
							</Button>
						</template>
					</EmailItem>
				</template>

				<template #item-comment="{ activity }">
					<CommentItem :comment="activity">
						<template v-if="withSlots" #actions>
							<Button
								variant="ghost"
								icon="trash-2"
								@click="log('delete', activity.data.name)"
							/>
						</template>
					</CommentItem>
				</template>

				<!-- a consumer-defined type, rendered entirely through its slot -->
				<template #item-feedback="{ activity }">
					<div class="rounded-md bg-surface-gray-2 px-3 py-2 text-p-sm text-ink-gray-7">
						Feedback — ★ {{ asFeedback(activity).rating }}/5 ·
						{{ asFeedback(activity).message }}
					</div>
				</template>
				<template #icon-feedback>
					<LucideStar class="size-4 text-ink-amber-3" />
				</template>
			</ActivityTimeline>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { Button, Switch } from "frappe-ui";
import LucideReply from "~icons/lucide/reply";
import LucideStar from "~icons/lucide/star";
import { ActivityTimeline, CommentItem, EmailItem } from "../index";
import type { Activity, CustomActivity, Pagination } from "../types";

const loading = ref(false);
const empty = ref(false);
const paginated = ref(false);
const withSlots = ref(true);

const person = (fullname: string, email?: string) => ({ fullname, email, image: "" });

// one of each activity type, in display order (oldest-first, as the composable emits)
const fixtures: Array<Activity | CustomActivity> = [
	{
		type: "log",
		key: "creation",
		timestamp: "2026-06-28 09:00:00",
		author: person("Jane Doe", "jane@example.com"),
		data: { name: "creation", subtype: "created", text: "Jane Doe created this document" },
	},
	{
		type: "version",
		key: "version:v1-0",
		timestamp: "2026-06-28 09:05:00",
		author: person("Jane Doe", "jane@example.com"),
		data: {
			name: "v1-0",
			fieldname: "status",
			type: "diff",
			prefix: "changed Status",
			from: "Open",
			to: "Replied",
		},
	},
	{
		type: "email",
		key: "email:E1",
		timestamp: "2026-06-28 10:00:00",
		author: person("Acme Support", "support@acme.com"),
		data: {
			name: "E1",
			subject: "Re: Login issue",
			sender: "support@acme.com",
			to: "jane@example.com",
			cc: "",
			bcc: "",
			content: "<p>Hi Jane, could you share a screenshot of the error?</p>",
			deliveryStatus: "Sent",
			attachments: [],
		},
	},
	{
		type: "comment",
		key: "comment:C1",
		timestamp: "2026-06-28 10:30:00",
		author: person("John Agent", "john@example.com"),
		data: { name: "C1", content: "<p>Escalating to tier 2.</p>" },
	},
	{
		type: "log",
		key: "log:A1",
		timestamp: "2026-06-28 11:00:00",
		author: person("John Agent", "john@example.com"),
		data: {
			name: "A1",
			subtype: "assigned",
			text: "John Agent assigned Priya Nair: please review",
			assignee: "Priya Nair",
		},
	},
	{
		type: "attachment_log",
		key: "attachment:AT1",
		timestamp: "2026-06-28 11:15:00",
		author: person("Priya Nair", "priya@example.com"),
		data: {
			name: "AT1",
			action: "added",
			fileName: "screenshot.png",
			fileUrl: "/files/screenshot.png",
			isPrivate: false,
		},
	},
	{
		type: "log",
		key: "log:L1",
		timestamp: "2026-06-28 11:30:00",
		author: person("Priya Nair", "priya@example.com"),
		data: { name: "L1", subtype: "like", text: "Priya Nair liked" },
	},
	{
		type: "feedback",
		key: "feedback:1",
		timestamp: "2026-06-28 12:00:00",
		author: person("Jane Doe", "jane@example.com"),
		data: { rating: 5, message: "Quick and helpful, thanks!" },
	},
];

// loading spinner / empty state only show when there are no rows, so each toggle clears the feed
const activities = computed<Array<Activity | CustomActivity>>(() =>
	empty.value || loading.value ? [] : fixtures
);

// a mock of the paginate controller useActivityTimeline() returns — no-op verbs
const paginate = reactive<Pagination>({
	hasNextPage: true,
	isFetchingNextPage: false,
	fetchNextPage: () => log("fetchNextPage"),
	loadMore: {
		position: "inline",
		label: "Show previous conversations",
		icon: "lucide-chevrons-up",
	},
});

// custom-type rows carry `unknown` data — narrow it for the demo slot
const asFeedback = (activity: Activity | CustomActivity) =>
	activity.data as { rating: number; message: string };

const log = (...args: unknown[]) => console.log(...args);
</script>
