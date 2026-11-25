<script setup lang="ts">
import type { ProfileGroupProps } from "./types";

defineProps<ProfileGroupProps>();
</script>

<template>
	<section data-slot="profile-group">
		<div
			v-if="label"
			data-slot="profile-group-label"
			class="mb-2 pl-4 text-lg-medium text-ink-gray-5"
		>
			{{ label }}
		</div>
		<nav class="overflow-hidden rounded-7 bg-surface-base">
			<slot />
		</nav>
	</section>
</template>
