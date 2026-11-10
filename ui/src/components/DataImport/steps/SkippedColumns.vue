<template>
	<div class="flex">
		<HoverCard :hover-delay="250" :leave-delay="150">
			<template #trigger>
				<slot>
					<button
						type="button"
						data-slot="skipped-columns"
						class="flex items-center gap-1.5 text-sm text-ink-gray-6 hover:text-ink-gray-8"
					>
						<span class="lucide-columns-3 size-4 shrink-0" />
						<span class="underline decoration-dotted underline-offset-2">
							{{
								columns.length === 1
									? t("1 column skipped")
									: t("{0} columns skipped", [columns.length])
							}}
						</span>
					</button>
				</slot>
			</template>
			<div class="flex max-w-sm flex-col gap-2 p-2">
				<p class="text-sm text-ink-gray-6">
					{{
						t(
							"These columns won't be imported. Map them in the Map columns step to import them."
						)
					}}
				</p>
				<div class="flex flex-wrap gap-1.5">
					<Badge
						v-for="column in columns"
						:key="column.col"
						:label="column.label"
						theme="gray"
					/>
				</div>
			</div>
		</HoverCard>
	</div>
</template>

<script setup lang="ts">
import { Badge, HoverCard } from "frappe-ui";
import { t } from "../translate";

defineProps<{ columns: { col: number; label: string }[] }>();
</script>
