<template>
	<!-- ps-[13px] aligns row text with the card text (1px border + px-3) -->
	<div
		class="flex flex-1 flex-col gap-2 ps-[13px] text-sm font-medium leading-6 text-ink-gray-6"
	>
		<!-- grouped: collapsible "Show +N changes" header -->
		<div v-if="changes.length > 1" class="flex items-center gap-1.5">
			<button
				type="button"
				class="flex items-center gap-2 hover:text-ink-gray-7"
				@click="expanded = !expanded"
			>
				<span class="text-ink-gray-5">
					<span>Show</span>
					<span class="font-medium text-ink-gray-8">
						+{{ changes.length }} changes
					</span>
					from
					<span class="font-medium text-ink-gray-8">{{ authorName }}</span>
				</span>
				<FeatherIcon :name="expanded ? 'chevron-up' : 'chevron-down'" class="size-3.5" />
			</button>
			<div class="ms-auto whitespace-nowrap">
				<Tooltip :text="dateFormat(activity.timestamp)">
					<span class="text-sm text-ink-gray-5">{{ timeAgo(activity.timestamp) }}</span>
				</Tooltip>
			</div>
		</div>

		<!-- change list: single shown always, group on expand -->
		<div v-if="changes.length === 1 || expanded" class="flex flex-col gap-2">
			<div v-for="change in changes" :key="change.name" class="flex flex-col gap-2">
				<div class="flex items-start gap-1.5">
					<!-- author leads only for a single change; the group header names them -->
					<span v-if="changes.length === 1" class="font-medium text-ink-gray-8">{{
						authorName
					}}</span>
					<span
						class="inline-flex flex-wrap items-center gap-1.5 text-ink-gray-5"
						:class="{ 'min-w-0 flex-1': changes.length === 1 }"
					>
						<!-- diff: prefix + from → to (arrow only when there's a `from`) -->
						<template v-if="change.type === 'diff'">
							<span :class="{ 'cap-first': changes.length > 1 }">{{
								change.prefix
							}}</span>
							<template v-if="change.from != null">
								<span
									class="font-semibold text-ink-gray-8"
									:title="truncate(change.from).title"
									>{{ truncate(change.from).text }}</span
								>
								<span class="text-ink-gray-5">→</span>
							</template>
							<span
								class="font-semibold text-ink-gray-8"
								:title="truncate(change.to).title"
								>{{ truncate(change.to).text }}</span
							>
							<!-- chevron reveals this field's change history -->
							<button
								v-if="hasHistory(change)"
								type="button"
								class="text-ink-gray-5 hover:text-ink-gray-7"
								@click="toggle(change.name)"
							>
								<FeatherIcon
									:name="isOpen(change.name) ? 'chevron-up' : 'chevron-down'"
									class="size-3.5"
								/>
							</button>
						</template>
						<!-- phrase: finished, value-less line -->
						<template v-else>
							<span :class="{ 'cap-first': changes.length > 1 }">{{
								change.text
							}}</span>
						</template>
					</span>
					<!-- single-change timeago inline; group puts it in the header -->
					<div v-if="changes.length === 1" class="ms-auto whitespace-nowrap">
						<Tooltip :text="dateFormat(activity.timestamp)">
							<span class="text-sm text-ink-gray-5">{{
								timeAgo(activity.timestamp)
							}}</span>
						</Tooltip>
					</div>
				</div>

				<!-- field history: nested mini-timeline, revealed by the chevron -->
				<div v-if="isOpen(change.name) && hasHistory(change)" class="flex flex-col gap-2">
					<div
						v-for="(hop, idx) in historyOf(change)"
						:key="idx"
						class="grid grid-cols-[16px_minmax(0,1fr)] gap-2"
					>
						<div class="relative">
							<div
								v-if="idx !== historyOf(change).length - 1"
								class="absolute start-1/2 top-3 h-full w-px -translate-x-1/2 bg-[var(--outline-gray-modals)]"
							/>
							<div class="relative z-10 flex h-6 items-center justify-center">
								<span
									class="flex size-4 items-center justify-center rounded-full bg-surface-white"
								>
									<DotIcon class="size-2 text-ink-gray-3" />
								</span>
							</div>
						</div>
						<div class="flex flex-wrap items-center gap-1.5 leading-6 text-ink-gray-5">
							<span class="font-medium text-ink-gray-8">{{ authorName }}</span>
							<span>{{ prefixOf(change) }}</span>
							<span
								v-if="hop.from"
								class="font-semibold text-ink-gray-8"
								:title="truncate(hop.from).title"
								>{{ truncate(hop.from).text }}</span
							>
							<span v-else class="text-ink-gray-5">""</span>
							<span>→</span>
							<span
								class="font-semibold text-ink-gray-8"
								:title="truncate(hop.to).title"
								>{{ truncate(hop.to).text }}</span
							>
							<span>·</span>
							<Tooltip :text="dateFormat(hop.timestamp)">
								<span class="text-ink-gray-5">{{ timeAgo(hop.timestamp) }}</span>
							</Tooltip>
						</div>
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { FeatherIcon, Tooltip } from "frappe-ui";
import { computed, reactive, ref } from "vue";
import { DotIcon } from "./icons";
import type { FieldChange, VersionActivity, VersionChange } from "./types";
import { dateFormat, timeAgo, truncate } from "./utils";

const props = defineProps<{
	activity: VersionActivity;
}>();

// folded run → list of changes; lone change → list of one
const changes = computed<VersionChange[]>(
	() => props.activity.data.group ?? [props.activity.data]
);

const authorName = computed(() => props.activity.author?.fullname ?? "");

// collapsible "+N changes" group toggle
const expanded = ref(false);

// per-change history panels, keyed by change.name
const openChanges = reactive(new Set<string>());
const isOpen = (name: string) => openChanges.has(name);
function toggle(name: string) {
	if (openChanges.has(name)) openChanges.delete(name);
	else openChanges.add(name);
}

// a diff with >1 save carries a chevron + history panel
const hasHistory = (change: VersionChange): boolean =>
	change.type === "diff" && (change.history?.length ?? 0) > 1;
const historyOf = (change: VersionChange): FieldChange[] =>
	change.type === "diff" ? change.history ?? [] : [];
const prefixOf = (change: VersionChange): string => (change.type === "diff" ? change.prefix : "");
</script>

<style scoped>
/* grouped net-change lines lead with the verb; capitalize only its first letter (locale-safe) */
.cap-first::first-letter {
	text-transform: capitalize;
}
</style>
