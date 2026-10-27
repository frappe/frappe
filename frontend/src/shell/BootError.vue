<template>
	<div class="flex h-full w-full flex-col items-center justify-center gap-2 p-8 text-center">
		<p class="text-lg font-medium text-ink-gray-8">{{ __("Something went wrong") }}</p>
		<p class="text-sm text-ink-gray-6">{{ __("The desk could not start.") }}</p>
		<a class="mt-2 text-sm text-ink-blue-3 hover:underline" href="/apps">{{
			__("Back to apps")
		}}</a>
	</div>
</template>

<script setup lang="ts">
import { __ } from "@/i18n";
</script>
