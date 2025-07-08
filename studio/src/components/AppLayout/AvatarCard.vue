<template>
	<div
		@click="
			() => {
				if (route) $router.push(route)
			}
		"
		class="mb-2 flex w-full items-center justify-center overflow-hidden rounded-lg border border-gray-200 p-2"
	>
		<Avatar :image="imageURL" size="2xl" shape="square" />
		<div class="flex-grow pl-2">
			<h2 class="truncate text-lg font-semibold text-gray-800">{{ title }}</h2>
			<p class="mt-1 truncate text-sm text-gray-600">{{ subtitle }}</p>
		</div>
		<button @click="toggleLike" class="ml-4 text-gray-600 transition-colors duration-200 hover:text-gray-800">
			<FeatherIcon name="heart" class="h-5 w-5" :class="isLiked ? 'fill-green-500' : 'stroke-current'" />
		</button>
	</div>
</template>

<script setup lang="ts">
import { Avatar, FeatherIcon } from "frappe-ui"
import { ref } from "vue"

import type { AvatarCardProps } from "@/types/studio_components/AvatarCard"

defineProps<AvatarCardProps>()

const isLiked = ref(false)

const toggleLike = () => {
	isLiked.value = !isLiked.value
}
</script>
