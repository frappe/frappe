<template>
	<div class="mb-2 flex w-full items-center justify-center overflow-hidden rounded-lg bg-gray-900 p-2">
		<Avatar :image="imageURL" size="2xl" shape="square" />
		<div class="flex-grow pl-2">
			<h2 class="truncate text-lg font-semibold text-white">{{ title }}</h2>
			<p class="mt-1 truncate text-sm text-gray-400">{{ subtitle }}</p>
		</div>
		<button @click="toggleLike" class="ml-4 text-gray-400 transition-colors duration-200 hover:text-white">
			<svg
				:class="{ 'text-green-500': isLiked }"
				class="h-6 w-6"
				fill="none"
				stroke="currentColor"
				viewBox="0 0 24 24"
				xmlns="http://www.w3.org/2000/svg"
			>
				<path
					stroke-linecap="round"
					stroke-linejoin="round"
					stroke-width="2"
					d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"
				/>
			</svg>
		</button>
	</div>
</template>

<script setup lang="ts">
import { Avatar } from "frappe-ui"
import { ref } from "vue"

import { AvatarCard } from "@/types/studioComponents"

defineProps<AvatarCard>()

const isLiked = ref(false)

const toggleLike = () => {
	isLiked.value = !isLiked.value
}
</script>
