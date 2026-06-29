<template>
	<!-- each field change as a nested activity row: gutter dot + sentence + timeago -->
	<div class="flex flex-col">
		<div
			v-for="(fieldChange, idx) in history"
			:key="idx"
			class="grid grid-cols-[16px_minmax(0,1fr)] gap-2"
		>
			<div class="relative">
				<div
					v-if="idx !== history.length - 1"
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
			<div class="flex flex-wrap items-center gap-1.5 pb-2 leading-6 text-ink-gray-5">
				<span class="font-medium text-ink-gray-8">{{ author }}</span>
				<span>{{ prefix }}</span>
				<span
					v-if="fieldChange.from"
					class="font-semibold text-ink-gray-8"
					:title="full(fieldChange.from)"
					>{{ clip(fieldChange.from) }}</span
				>
				<span v-else class="text-ink-gray-5">""</span>
				<span>→</span>
				<span class="font-semibold text-ink-gray-8" :title="full(fieldChange.to)">{{
					clip(fieldChange.to)
				}}</span>
				<span>·</span>
				<Tooltip :text="dateFormat(fieldChange.timestamp)">
					<span class="text-ink-gray-5">{{ timeAgo(fieldChange.timestamp) }}</span>
				</Tooltip>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Tooltip } from "frappe-ui";
import { DotIcon } from "./icons";
import type { FieldChange } from "./types";
import { dateFormat, timeAgo } from "./utils";

defineProps<{ history: FieldChange[]; author: string; prefix: string }>();

const LIMIT = 40;
const clip = (v?: string) => ((v?.length ?? 0) > LIMIT ? v!.slice(0, LIMIT) + "…" : v ?? "");
const full = (v?: string) => ((v?.length ?? 0) > LIMIT ? v : undefined);
</script>
