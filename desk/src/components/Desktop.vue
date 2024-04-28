<template>
	<div class="my-5 w-full max-w-5xl">
		<div class="grid grid-cols-[repeat(5,_60px)] justify-between gap-y-13">
			<template v-for="item in desktopModules.data?.pages">
				<!-- Module Link -->
				<router-link to="/" class="mt-5 flex flex-col items-center justify-center gap-2">
					<div class="rounded-lg border border-gray-400 p-3 hover:scale-110">
						<Icon :name="item.icon" class="h-8 w-8 text-gray-500" />
					</div>
					<span class="text-base text-gray-600">{{ item.label }}</span>
				</router-link>
			</template>
		</div>
	</div>
</template>

<script setup>
import { desktopModules } from "@/data/desktop"
import Icon from "@/components/Icon.vue"
</script>
