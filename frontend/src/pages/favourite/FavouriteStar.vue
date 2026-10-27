<!-- The favourite star the record and list headers draw: a ghost button, filled while favourited. -->
<template>
	<Button
		variant="ghost"
		:label="favourited ? __('Remove from favourites') : __('Add to favourites')"
		:aria-pressed="favourited"
		data-favourite
	>
		<template #icon>
			<!-- Drawn here, not off a lucide mask, so the favourited stroke can thicken. -->
			<svg
				class="size-4"
				:class="favourited ? 'fill-ink-amber-4 stroke-ink-amber-4' : 'text-ink-gray-7'"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				:stroke-width="favourited ? 2.5 : 1.5"
				stroke-linecap="round"
				stroke-linejoin="round"
				aria-hidden="true"
			>
				<path
					d="M12 2.5l2.9 5.88 6.6.96-4.75 4.63 1.12 6.53L12 17.4l-5.87 3.1 1.12-6.53L2.5 9.34l6.6-.96z"
				/>
			</svg>
		</template>
	</Button>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui";
import { __ } from "@/i18n";

defineProps<{ favourited: boolean }>();
</script>
