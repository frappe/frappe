<script setup lang="ts">
import { computed, ref } from "vue";
import { PhoneInput } from "frappe-ui";

const phone = ref("+91-9876543210");

const isVerified = computed(() => {
	const number = phone.value.split("-")[1] ?? "";
	return number.length >= 10;
});
</script>

<template>
	<PhoneInput v-model="phone" label="WhatsApp number" class="w-72">
		<template #suffix>
			<span v-if="isVerified" class="lucide-circle-check size-4 text-ink-green-3" />
		</template>
	</PhoneInput>
</template>
