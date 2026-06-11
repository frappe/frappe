<script setup lang="ts">
import { ref } from "vue";
import { PhoneInput } from "frappe-ui";

const usOffice = ref("");
const ukOffice = ref("");
const tokyoOffice = ref("");
</script>

<template>
	<div class="flex w-full max-w-sm flex-col gap-4">
		<!-- ISO2 code -->
		<PhoneInput v-model="usOffice" label="US office" default-country="us" />
		<!-- Dial code, with or without the + -->
		<PhoneInput v-model="ukOffice" label="UK office" default-country="+44" />
		<!-- Country name -->
		<PhoneInput v-model="tokyoOffice" label="Tokyo office" default-country="Japan" />
	</div>
</template>
