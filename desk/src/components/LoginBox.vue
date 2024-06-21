<template>
	<div class="relative h-full">
		<div class="relative z-10 mx-auto py-8 sm:w-max sm:py-32">
			<div class="flex">
				<div class="mx-auto flex flex-col items-center gap-4 space-x-2">
					<AppLogo class="inline-block h-8 w-8" />
					<span class="text-xl font-semibold leading-5 tracking-wide text-gray-900">
						{{ title }}
					</span>
				</div>
			</div>

			<!-- Login Form -->
			<slot></slot>
		</div>
	</div>
</template>

<script setup lang="ts">
import AppLogo from "@/components/Icons/AppLogo.vue"

withDefaults(defineProps<{ title: string }>(), { title: "Login" })
</script>
