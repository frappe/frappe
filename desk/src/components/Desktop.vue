<template>
	<div class="my-12 w-full max-w-5xl">
		<div
			class="grid grid-cols-3 justify-between gap-y-13 md:grid-cols-4 lg:grid-cols-[repeat(6,_60px)]"
		>
			<template v-for="item in desktopModules.data?.pages">
				<!-- Module Link -->
				<router-link to="/" class="mt-5 flex flex-col items-center justify-center gap-3">
					<div class="rounded-lg border border-gray-500 p-3 hover:scale-110">
						<Icon :name="item.icon" class="h-8 w-8 text-gray-600" />
					</div>
					<span class="truncate text-base text-gray-800">{{ item.label }}</span>
				</router-link>
			</template>
		</div>
	</div>
</template>
<script setup>
import { desktopModules } from "@/data/desktop"
import Icon from "@/components/Icon.vue"
</script>
