<script setup lang="ts">
import { PhoneInput } from "frappe-ui";
</script>

<template>
	<div class="flex w-full max-w-sm flex-col gap-3">
		<PhoneInput size="sm" placeholder="Small" />
		<PhoneInput size="md" placeholder="Medium" />
		<PhoneInput size="lg" placeholder="Large" />
		<PhoneInput size="xl" placeholder="Extra large" />
	</div>
</template>
