<template>
	<header class="sticky top-0 z-10 flex w-full flex-col items-center border-b bg-white px-5 py-2.5">
		<div class="w-full">
			<div class="flex w-full items-center">
				<div class="flex cursor-pointer items-center gap-2">
					<template v-if="!hideLogo">
						<div v-if="logoSVG" class="flex items-center gap-2">
							<span v-html="logoSVG" />
						</div>
						<AppLogo v-else class="h-6 w-6" />
					</template>
					<h1 v-if="title" class="text-md font-semibold leading-5 text-gray-800">{{ title }}</h1>
				</div>

				<div class="ml-auto flex flex-row items-center gap-2" v-if="!hideMenu">
					<template v-for="item in menuItems" :key="item.label">
						<div class="flex cursor-pointer items-center gap-2" @click="item.action">
							<span class="text-base text-gray-800">{{ item.label }}</span>
						</div>
					</template>
				</div>

				<slot></slot>
			</div>
		</div>
	</header>
</template>

<script setup lang="ts">
import AppLogo from "../Icons/AppLogo.vue"
import type { HeaderProps } from "@/types/studio_components/Header"

withDefaults(defineProps<HeaderProps>(), {
	menuItems: () => [],
})
</script>
