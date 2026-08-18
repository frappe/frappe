<script setup lang="ts">
import { ref } from "vue";
import { PhoneInput } from "frappe-ui";

const phone = ref("");
</script>

<template>
	<div class="flex w-full max-w-sm flex-col gap-2">
		<PhoneInput v-model="phone" placeholder="98765 43210" />
		<p class="text-p-sm text-ink-gray-5">v-model: {{ phone || "—" }}</p>
	</div>
</template>
