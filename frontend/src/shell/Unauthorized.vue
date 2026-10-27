<template>
	<div
		class="flex h-screen w-screen flex-col items-center justify-center gap-2 bg-surface-base p-8 text-center"
	>
		<p class="text-lg font-medium text-ink-gray-8">{{ __("Not permitted") }}</p>
		<p class="text-sm text-ink-gray-6">{{ __("You do not have access to this app.") }}</p>
		<a
			class="mt-2 text-sm text-ink-gray-8 underline hover:text-ink-gray-9"
			:href="exit.href"
			>{{ exit.label }}</a
		>
	</div>
</template>

<script setup lang="ts">
import { __ } from "@/i18n";

// At the index, `/apps` is the page that refused; `/me` is where the server sends such a user.
const onIndex = location.pathname.replace(/\/+$/, "") === "/apps";
const exit = onIndex
	? { href: "/me", label: __("Go to my account") }
	: { href: "/apps", label: __("Back to apps") };
</script>
