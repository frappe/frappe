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
				<LucideChevronUp v-if="expanded" class="size-3.5" />
				<LucideChevronDown v-else class="size-3.5" />
			</button>
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
								<Tooltip :text="truncate(change.from).title">
									<span class="font-semibold text-ink-gray-8">{{
										truncate(change.from).text
									}}</span>
								</Tooltip>
								<span class="text-ink-gray-5">→</span>
							</template>
							<Tooltip :text="truncate(change.to).title">
								<span class="font-semibold text-ink-gray-8">{{
									truncate(change.to).text
								}}</span>
							</Tooltip>
							<!-- chevron reveals this field's change history -->
							<button
								v-if="hasHistory(change)"
								type="button"
								class="text-ink-gray-5 hover:text-ink-gray-7"
								@click="toggle(change.name)"
							>
								<LucideChevronUp v-if="isOpen(change.name)" class="size-3.5" />
								<LucideChevronDown v-else class="size-3.5" />
							</button>
						</template>
						<!-- phrase: finished, value-less line -->
						<template v-else>
							<span :class="{ 'cap-first': changes.length > 1 }">{{
								change.text
							}}</span>
						</template>
					</span>
					<!-- per-change time; the group header still shows the overall time -->
					<div class="ms-auto whitespace-nowrap">
						<TimeAgo
							:timestamp="change.timestamp ?? activity.timestamp"
							class="text-sm"
						/>
					</div>
				</div>

				<!-- field history: revealed by the chevron; single continuous line, no dots -->
				<div
					v-if="isOpen(change.name) && hasHistory(change)"
					class="relative ms-2 flex flex-col gap-2 ps-4"
				>
					<!-- inset half a row (leading-6 ÷ 2) so the line spans first→last entry centers -->
					<div class="absolute inset-y-3 start-0 w-px bg-[var(--outline-gray-modals)]" />
					<div
						v-for="(historyEntry, idx) in historyOf(change)"
						:key="idx"
						class="flex flex-wrap items-center gap-1.5 leading-6 text-ink-gray-5"
					>
						<span class="font-medium text-ink-gray-8">{{ authorName }}</span>
						<span>{{ prefixOf(change) }}</span>
						<Tooltip
							v-if="historyEntry.from"
							:text="truncate(historyEntry.from).title"
						>
							<span class="font-semibold text-ink-gray-8">{{
								truncate(historyEntry.from).text
							}}</span>
						</Tooltip>
						<span v-else class="text-ink-gray-5">""</span>
						<span>→</span>
						<Tooltip :text="truncate(historyEntry.to).title">
							<span class="font-semibold text-ink-gray-8">{{
								truncate(historyEntry.to).text
							}}</span>
						</Tooltip>
						<span>·</span>
						<TimeAgo :timestamp="historyEntry.timestamp" />
					</div>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Tooltip } from "frappe-ui";
import { computed, reactive, ref } from "vue";
import TimeAgo from "./TimeAgo.vue";
import type { FieldChange, VersionActivity, VersionChange } from "./types";
import { truncate } from "./utils";

const props = defineProps<{
	activity: VersionActivity;
}>();

// folded run → list of changes; lone change → list of one
const changes = computed<VersionChange[]>(
	() => props.activity.data.group ?? [props.activity.data]
);

const authorName = computed(() => props.activity?.author?.fullname ?? "");

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
