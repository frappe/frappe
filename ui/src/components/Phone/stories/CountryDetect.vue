<script setup lang="ts">
import { ref } from "vue";
import { Button, PhoneInput } from "frappe-ui";

const phone = ref("");

const customers = [
	{ name: "Sofia (UK)", phone: "+44-2079460958" },
	{ name: "Marcus (US)", phone: "+1-4155550132" },
	{ name: "Priya (India)", phone: "+91-9876543210" },
];
</script>

<template>
	<div class="flex w-full max-w-sm flex-col gap-3">
		<PhoneInput v-model="phone" label="Customer phone" />
		<div class="flex gap-2">
			<Button
				v-for="customer in customers"
				:key="customer.name"
				variant="outline"
				@click="phone = customer.phone"
			>
				{{ customer.name }}
			</Button>
		</div>
		<p class="text-p-sm text-ink-gray-5">
			Pasting a full international number ("+442079460958") into the input flips the country
			too.
		</p>
	</div>
</template>
