<script setup>
import { computed, inject, onMounted, ref } from "vue";
import { usePanelHeader } from "../panel";
import BillingProfileCard from "./BillingProfileCard.vue";
import AddPaymentCard from "./AddPaymentCard.vue";
import TopUpCard from "./TopUpCard.vue";

const store = inject("store");

usePanelHeader(__("Billing"), __("Your plan, usage, credit and payment method."));
onMounted(async () => {
	// A card added on the gateway's hosted page activates on return — no webhook
	// needed. Cheap server-side when nothing is pending.
	try {
		await store.api.reconcilePaymentSetup();
	} catch (exception) {
		// non-fatal — the summary still loads
	}
	store.loadBilling(true);
});

const billing = computed(() => store.state.billing);
const error = computed(() => store.state.billingError);

// One inline flow open at a time: "" | "profile" | "payment" | "topup".
// Changing the plan isn't offered in-app yet (see the plan card) — it's a
// downtime-bearing VM resize that Central must host.
const flow = ref("");
const removing = ref(false);

const paymentTitle = computed(() =>
	billing.value?.payment_method
		? billing.value.payment_method.label
		: __("No payment method yet")
);

const paymentSubtitle = computed(() =>
	billing.value?.payment_method
		? __("Used for your monthly bill.")
		: __("You're on trial credit. Add a payment method to keep this site running after it.")
);

// Billing details must exist before a payment method; route the button accordingly.
function startPayment() {
	flow.value = billing.value?.profile_complete ? "payment" : "profile";
}

// Top-up also moves money, so it needs a complete billing profile first.
function startTopup() {
	flow.value = billing.value?.profile_complete ? "topup" : "profile";
}

// Once details are saved, continue straight into adding a payment method.
function afterProfile() {
	flow.value = "payment";
}

async function removeCard() {
	if (!billing.value?.payment_method || removing.value) return;

	removing.value = true;
	store.state.billingError = "";
	try {
		await store.api.removePaymentMethod(billing.value.payment_method.name);
		await store.loadBilling(true);
	} catch (exception) {
		store.state.billingError = store.api.getErrorMessage(exception);
	} finally {
		removing.value = false;
	}
}

function clamp(percent) {
	return `${Math.max(0, Math.min(100, Number(percent) || 0))}%`;
}
</script>

<template>
	<div>
		<div v-if="error" class="cloud-settings-alert error">
			<svg class="icon icon-sm"><use href="#icon-triangle-alert"></use></svg>
			<span>{{ error }}</span>
		</div>
		<div v-else-if="!billing" class="cloud-settings-state">{{ __("Loading") }}</div>

		<div v-else-if="!billing.plan" class="cloud-settings-payment">
			<div class="cloud-settings-payment-row">
				<svg class="icon icon-sm"><use href="#icon-wallet"></use></svg>
				<div>
					<div class="cloud-settings-title-lg" style="font-size: var(--text-base)">
						{{ __("Billing isn't available for this site yet") }}
					</div>
					<p class="cloud-settings-sub">
						{{ __("This site isn't connected to a billing account, or the connection isn't ready.") }}
					</p>
				</div>
			</div>
		</div>

		<div v-else class="cloud-settings-stack">
			<div class="cloud-settings-card">
				<div class="cloud-settings-card-head">
					<div>
						<div class="cloud-settings-label">{{ __("Plan") }}</div>
						<div class="cloud-settings-title-lg">{{ billing.plan.name }}</div>
						<p class="cloud-settings-sub">{{ billing.plan.subtitle }}</p>
					</div>
					<!-- Change plan is intentionally not offered in-app yet: a live plan
					  change is a downtime-bearing VM resize that Central must host, and a
					  redirect needs a signed pilot→Central SSO link (not built). Until then
					  the plan is read-only here. -->
				</div>

				<div class="cloud-settings-usage">
					<div v-for="meter in billing.usage" :key="meter.name">
						<div class="cloud-settings-meter-top">
							<span class="name">{{ meter.name }}</span>
							<span class="pct">{{ meter.percent }}%</span>
						</div>
						<div class="cloud-settings-bar">
							<span :style="{ width: clamp(meter.percent) }"></span>
						</div>
						<div class="cloud-settings-meter-detail">{{ meter.detail }}</div>
					</div>
				</div>
			</div>

			<div class="cloud-settings-grid-2">
				<div class="cloud-settings-card">
					<div class="cloud-settings-label">{{ __("Estimated this cycle") }}</div>
					<div class="cloud-settings-value">{{ billing.estimate.amount }}</div>
					<div class="cloud-settings-note">{{ billing.estimate.note }}</div>
				</div>
				<div class="cloud-settings-card">
					<div class="cloud-settings-label">{{ __("Trial credit") }}</div>
					<div class="cloud-settings-value">{{ billing.credit.amount }}</div>
					<div class="cloud-settings-note" :class="{ warning: billing.credit.warning }">
						<svg v-if="billing.credit.warning" class="icon icon-xs">
							<use href="#icon-triangle-alert"></use>
						</svg>
						{{ billing.credit.note }}
					</div>
					<button class="btn btn-sm btn-default" style="margin-top: 12px" :disabled="flow === 'topup'"
						@click="startTopup">
						<svg class="icon icon-xs"><use href="#icon-plus"></use></svg>
						{{ __("Add credit") }}
					</button>
				</div>
			</div>

			<BillingProfileCard v-if="flow === 'profile'" @close="flow = ''" @saved="afterProfile" />
			<AddPaymentCard v-else-if="flow === 'payment'" :billing="billing" @close="flow = ''" />
			<TopUpCard v-else-if="flow === 'topup'" @close="flow = ''" />

			<div v-else class="cloud-settings-payment cloud-settings-payment--row">
				<div class="cloud-settings-payment-row">
					<svg class="icon icon-sm"><use href="#icon-credit-card"></use></svg>
					<div>
						<div class="cloud-settings-title-lg" style="font-size: var(--text-base)">
							{{ paymentTitle }}
						</div>
						<p class="cloud-settings-sub">{{ paymentSubtitle }}</p>
					</div>
				</div>
				<div class="cloud-settings-actions">
					<button v-if="billing.payment_method" class="btn btn-sm btn-default" :disabled="removing"
						@click="removeCard">
						{{ __("Remove") }}
					</button>
					<button v-else class="btn btn-sm btn-primary" @click="startPayment">
						<svg class="icon icon-xs"><use href="#icon-plus"></use></svg>
						{{ billing.profile_complete ? __("Add") : __("Add billing details") }}
					</button>
				</div>
			</div>
		</div>
	</div>
</template>
