<!--
  TopUpCard — add wallet credit via hosted checkout. Central opens a Stripe Checkout
  Session / Razorpay Payment Link for the amount; we open it in a new tab, the payer
  completes it there, and the gateway's capture webhook credits the wallet (polling
  via "Check payment" reports the same, idempotently).
-->
<script setup>
import { computed, inject, ref } from "vue";

const emit = defineEmits(["close"]);
const store = inject("store");

const amount = ref(500);
const checkout = ref(null); // { checkout_url, reference, gateway }
const message = ref("");
const working = ref(false);
const error = ref("");

const billingCurrency = computed(() => store.state.billing?.currency || "");
const canStart = computed(() => Number(amount.value) > 0 && !working.value);

async function start() {
	if (!canStart.value) return;
	await run(async () => {
		checkout.value = await store.api.createTopupCheckout(Number(amount.value));
		message.value = __("Checkout opened in a new tab. Complete the payment there, then check its status.");
		window.open(checkout.value.checkout_url, "_blank", "noopener");
	});
}

async function check() {
	await run(async () => {
		const result = await store.api.getCheckoutStatus(checkout.value.reference);
		message.value = result.message || result.status;
		if (result.success) await store.loadBilling(true);
	});
}

async function run(action) {
	working.value = true;
	error.value = "";
	try {
		await action();
	} catch (exception) {
		error.value = store.api.getErrorMessage(exception);
	} finally {
		working.value = false;
	}
}
</script>

<template>
	<div class="cloud-settings-card cloud-settings-stack">
		<div class="cloud-settings-title-lg" style="font-size: var(--text-base)">
			{{ __("Add credit") }}
		</div>

		<div v-if="error" class="cloud-settings-alert error">
			<svg class="icon icon-sm"><use href="#icon-triangle-alert"></use></svg>
			<span>{{ error }}</span>
		</div>

		<div class="cloud-settings-field" style="max-width: 220px">
			<label>{{ __("Amount ({0})", [billingCurrency]) }}</label>
			<input v-model="amount" type="number" min="1" class="cloud-settings-input" :disabled="working || !!checkout" />
		</div>

		<p v-if="message" class="cloud-settings-help">{{ message }}</p>

		<div class="cloud-settings-actions" style="justify-content: flex-end">
			<button class="btn btn-sm btn-default" :disabled="working" @click="$emit('close')">
				{{ __("Cancel") }}
			</button>
			<a
				v-if="checkout"
				class="btn btn-sm btn-default"
				:href="checkout.checkout_url"
				target="_blank"
				rel="noopener"
			>
				{{ __("Reopen checkout") }}
			</a>
			<button v-if="checkout" class="btn btn-sm btn-primary" :disabled="working" @click="check">
				{{ __("Check payment") }}
			</button>
			<button v-else class="btn btn-sm btn-primary" :disabled="!canStart" @click="start">
				{{ __("Continue to checkout") }}
			</button>
		</div>
	</div>
</template>
