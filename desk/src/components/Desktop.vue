<template>
	<div class="my-12 w-full max-w-5xl">
		<div
			class="grid grid-cols-3 justify-between gap-y-13 md:grid-cols-4 lg:grid-cols-[repeat(6,_60px)]"
		>
			<template v-for="item in desktopItems.data">
				<!-- Module Link -->
				<router-link
					:to="{ name: 'Module', params: { module: item.module_slug } }"
					class="mt-5 flex flex-col items-center justify-center gap-3"
				>
					<div
						class="rounded-lg p-3 shadow-md hover:scale-110"
						:style="`background-color: ${item.color}`"
					>
						<Icon :name="item.icon" class="h-8 w-8 text-white" />
					</div>
					<span class="truncate text-base text-gray-800">{{ item.label }}</span>
				</router-link>
			</template>
		</div>
	</div>
</template>

<script setup>
import { desktopItems } from "@/data/desktop"
import Icon from "@/components/Icon.vue"
</script>
