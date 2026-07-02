<template>
	<div>
		<div v-if="error" class="cloud-settings-alert error">{{ error }}</div>
		<div v-else-if="!billing" class="cloud-settings-state">{{ __("Loading") }}</div>

		<div v-else-if="!billing.available" class="cloud-settings-payment">
			<div class="cloud-settings-payment-row">
				<svg class="icon icon-sm"><use href="#icon-wallet"></use></svg>
				<div>
					<div class="cloud-settings-title-lg" style="font-size: var(--text-base)">
						{{ __("Billing lives in your account console") }}
					</div>
					<p class="cloud-settings-sub">
						{{ __("Manage your plan, usage, credit and payment methods there.") }}
					</p>
				</div>
			</div>
			<a
				v-if="billing.manage_url"
				class="btn btn-sm btn-primary"
				:href="billing.manage_url"
				target="_blank"
				rel="noopener"
			>
				{{ __("Manage billing") }}
				<svg class="icon icon-xs"><use href="#icon-arrow-up-right"></use></svg>
			</a>
		</div>

		<div v-else class="cloud-settings-stack">
			<div class="cloud-settings-card">
				<div class="cloud-settings-card-head">
					<div>
						<div class="cloud-settings-label">{{ __("Plan") }}</div>
						<div class="cloud-settings-title-lg">{{ billing.plan.name }}</div>
						<p class="cloud-settings-sub">{{ billing.plan.subtitle }}</p>
					</div>
					<a
						v-if="billing.change_plan_url"
						class="btn btn-sm btn-default"
						:href="billing.change_plan_url"
						target="_blank"
						rel="noopener"
					>
						{{ __("Change plan") }}
					</a>
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
				</div>
			</div>

			<div class="cloud-settings-payment">
				<div class="cloud-settings-payment-row">
					<svg class="icon icon-sm"><use href="#icon-credit-card"></use></svg>
					<div>
						<div class="cloud-settings-title-lg" style="font-size: var(--text-base)">
							{{ paymentTitle }}
						</div>
						<p class="cloud-settings-sub">{{ paymentSubtitle }}</p>
					</div>
				</div>
				<a
					v-if="billing.add_payment_url"
					class="btn btn-sm btn-primary"
					:href="billing.add_payment_url"
					target="_blank"
					rel="noopener"
				>
					<svg class="icon icon-xs"><use href="#icon-plus"></use></svg>
					{{ __("Add payment method") }}
				</a>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, onMounted } from "vue";
import { usePanelHeader } from "../panel";

const store = inject("store");

usePanelHeader(__("Billing"), __("Your plan, usage, credit and payment method."));
onMounted(store.loadBilling);

const billing = computed(() => store.state.billing);
const error = computed(() => store.state.billingError);

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

function clamp(percent) {
	return `${Math.max(0, Math.min(100, Number(percent) || 0))}%`;
}
</script>
