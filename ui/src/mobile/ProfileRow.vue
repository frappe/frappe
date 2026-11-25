<script setup lang="ts">
import { Icon } from "frappe-ui";
import type { ProfileRowProps } from "./types";

defineProps<ProfileRowProps>();
</script>

<template>
	<button
		type="button"
		data-slot="profile-row"
		class="block w-full text-left transition active:bg-surface-gray-2 [&:first-child_[data-slot=profile-row-divider]]:hidden"
	>
		<!-- the flex layout is on this inner wrapper, not the button: iOS Safari wraps a
		     button's children in an anonymous box and top-aligns a flex button's rows -->
		<span class="flex min-h-14 w-full items-stretch">
			<span
				data-slot="profile-row-prefix"
				class="flex w-14 shrink-0 items-center justify-center py-3"
			>
				<slot name="prefix">
					<Icon :name="icon" class="size-5 text-ink-gray-8" />
				</slot>
			</span>
			<span class="relative flex min-w-0 flex-1 items-center gap-3 py-3 pr-4">
				<span
					data-slot="profile-row-divider"
					class="pointer-events-none absolute left-0 right-4 top-0 border-t"
					aria-hidden="true"
				/>
				<span
					data-slot="profile-row-label"
					class="min-w-0 flex-1 truncate text-lg text-ink-gray-9"
					>{{ label }}</span
				>
				<span
					v-if="value"
					data-slot="profile-row-value"
					class="max-w-[50%] shrink-0 truncate text-md text-ink-gray-5"
				>
					{{ value }}
				</span>
				<slot name="suffix">
					<span
						class="size-4 shrink-0 text-ink-gray-4 lucide-chevron-right"
						aria-hidden="true"
					/>
				</slot>
			</span>
		</span>
	</button>
</template>
