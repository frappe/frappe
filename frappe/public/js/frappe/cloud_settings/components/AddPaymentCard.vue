<!--
  AddPaymentCard — add a card via hosted setup checkout (mockup 4). The customer
  picks the payment type + gateway; Central opens a Stripe Checkout session in
  `setup` mode; we open it in a new tab, the card is saved on the gateway's page,
  and "Check status" validates it (micro-charge) → Active. No card data touches
  the site. Same shape as the top-up flow.
-->
<script setup>
import { computed, inject, onMounted, ref, watch } from "vue";

const emit = defineEmits(["close"]);
const store = inject("store");

const ASSETS = "/assets/frappe/images/cloud_settings/";
const GATEWAY_LOGO = { Stripe: "Stripe.svg", Razorpay: "Razorpay-1.svg" };
const RAZORPAY_SDK = "https://checkout.razorpay.com/v1/checkout.js";

const methods = [
	// Card uses the Lucide card glyph; UPI uses the brand wordmark.
	{
		value: "Card",
		label: __("Card"),
		hint: __("Visa, Mastercard, RuPay, Amex"),
		lucide: "credit-card",
	},
	{
		value: "UPI Autopay",
		label: __("UPI"),
		hint: __("Pay from any UPI app"),
		image: "UPI-1.svg",
	},
];

const gateways = ref(null);
const method = ref("Card");
const selected = ref("");
const contact = ref("");
const checkout = ref(null); // Stripe hosted-redirect handle
const message = ref("");
const working = ref(false);
const error = ref("");

onMounted(load);

// UPI is Razorpay-only; Card can go through any gateway serving the currency.
const visibleGateways = computed(() =>
	(gateways.value || []).filter(
		(g) => method.value !== "UPI Autopay" || g.adapter_key === "Razorpay"
	)
);
const selectedGateway = computed(() =>
	visibleGateways.value.find((g) => g.name === selected.value)
);
const continueLabel = computed(() =>
	selectedGateway.value ? __("Continue with {0}", [selectedGateway.value.label]) : __("Continue")
);
const canContinue = computed(() => !!selectedGateway.value && !working.value);
// Razorpay card mandates need a phone when the billing profile has none.
const needsContact = computed(
	() => method.value === "Card" && selectedGateway.value?.adapter_key === "Razorpay"
);

// Keep a valid gateway selected as the visible set changes (e.g. switching to UPI).
watch(
	visibleGateways,
	(list) => {
		if (!list.some((g) => g.name === selected.value)) selected.value = list[0]?.name || "";
	},
	{ immediate: true }
);

async function load() {
	error.value = "";
	try {
		gateways.value = await store.api.getPaymentGateways();
	} catch (exception) {
		error.value = store.api.getErrorMessage(exception);
	}
}

// Stripe saves a card via a hosted redirect; Razorpay authorises a recurring
// card/UPI mandate through its own Checkout modal (razorpay.js) — no redirect.
function start() {
	if (!canContinue.value) return;
	if (selectedGateway.value.adapter_key === "Razorpay") return startRazorpay();
	return startStripe();
}

async function startStripe() {
	await run(async () => {
		checkout.value = await store.api.createPaymentMethodCheckout(selected.value);
		message.value = __(
			"Checkout opened in a new tab. Add your card there, then check its status."
		);
		window.open(checkout.value.checkout_url, "_blank", "noopener");
	});
}

async function startRazorpay() {
	working.value = true;
	error.value = "";
	message.value = "";
	try {
		const handles = await store.api.addPaymentMethod(
			method.value,
			selected.value,
			contact.value.trim() || null
		);
		await loadRazorpay();
		openRazorpayCheckout(handles);
		// `working` stays true while the modal is open; dismiss/fail/success reset it.
	} catch (exception) {
		error.value = store.api.getErrorMessage(exception);
		working.value = false;
	}
}

function openRazorpayCheckout(handles) {
	const rzp = new window.Razorpay({
		key: handles.key_id,
		order_id: handles.order_id,
		customer_id: handles.customer_id,
		recurring: handles.recurring ? 1 : undefined,
		name: __("Frappe Cloud"),
		description:
			method.value === "UPI Autopay"
				? __("Set up UPI Autopay")
				: __("Save card for billing"),
		prefill: handles.prefill || {},
		handler: (response) => confirmRazorpay(handles.payment_method, response),
		modal: {
			ondismiss: () => {
				working.value = false;
				message.value = __("Setup cancelled.");
			},
		},
	});
	rzp.on("payment.failed", (response) => {
		error.value = response?.error?.description || __("Authorisation failed.");
		working.value = false;
	});
	rzp.open();
}

async function confirmRazorpay(paymentMethod, response) {
	await run(async () => {
		const result = await store.api.confirmPaymentMethod({
			payment_method: paymentMethod,
			razorpay_payment_id: response.razorpay_payment_id,
			razorpay_order_id: response.razorpay_order_id,
			razorpay_signature: response.razorpay_signature,
		});
		if (result.status === "Active") {
			await store.loadBilling(true);
			emit("close");
			return;
		}
		error.value = __("Saved but not active ({0}).", [result.status]);
	});
}

function loadRazorpay() {
	return new Promise((resolve, reject) => {
		if (window.Razorpay) return resolve();
		const script = document.createElement("script");
		script.src = RAZORPAY_SDK;
		script.onload = resolve;
		script.onerror = () => reject(new Error(__("Could not load Razorpay Checkout.")));
		document.body.appendChild(script);
	});
}

async function check() {
	await run(async () => {
		const result = await store.api.confirmPaymentMethodCheckout(checkout.value.reference);
		if (result.active) {
			await store.loadBilling(true);
			emit("close");
			return;
		}
		message.value =
			result.message || __("Not confirmed yet — finish adding the card, then check again.");
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
			{{ __("Add payment method") }}
		</div>

		<div v-if="error" class="cloud-settings-alert error">
			<svg class="icon icon-sm"><use href="#icon-triangle-alert"></use></svg>
			<span>{{ error }}</span>
		</div>

		<div class="cloud-settings-label">{{ __("Choose a payment method") }}</div>
		<div class="cloud-settings-segment">
			<button
				v-for="option in methods"
				:key="option.value"
				type="button"
				class="cloud-settings-segment-item"
				:class="{ selected: method === option.value }"
				:disabled="working || !!checkout"
				@click="method = option.value"
			>
				<span class="cloud-settings-logo-box">
					<svg v-if="option.lucide" class="icon">
						<use :href="`#icon-${option.lucide}`"></use>
					</svg>
					<img v-else :src="ASSETS + option.image" :alt="option.label" />
				</span>
				<span class="cloud-settings-pay-body">
					<span class="cloud-settings-segment-title">{{ option.label }}</span>
					<span class="cloud-settings-sub">{{ option.hint }}</span>
				</span>
			</button>
		</div>

		<div class="cloud-settings-label">{{ __("Pay through") }}</div>
		<div v-if="!gateways" class="cloud-settings-state" style="min-height: 60px">
			{{ __("Loading") }}
		</div>
		<div v-else-if="!visibleGateways.length" class="cloud-settings-sub">
			{{ __("No gateway available for this payment type.") }}
		</div>
		<div v-else class="cloud-settings-gateway-grid">
			<button
				v-for="gateway in visibleGateways"
				:key="gateway.name"
				type="button"
				class="cloud-settings-gateway"
				:class="{ selected: selected === gateway.name }"
				:disabled="working || !!checkout"
				@click="selected = gateway.name"
			>
				<span v-if="GATEWAY_LOGO[gateway.adapter_key]" class="cloud-settings-logo-box">
					<img :src="ASSETS + GATEWAY_LOGO[gateway.adapter_key]" :alt="gateway.label" />
				</span>
				<span v-else class="cloud-settings-gateway-avatar">{{
					gateway.label.charAt(0)
				}}</span>
				<span class="cloud-settings-gateway-body">
					<span class="cloud-settings-gateway-name">{{ gateway.label }}</span>
					<span class="cloud-settings-sub">{{ gateway.subtitle }}</span>
				</span>
			</button>
		</div>

		<div v-if="needsContact" class="cloud-settings-field">
			<label>{{ __("Phone") }}</label>
			<input
				v-model="contact"
				class="cloud-settings-input"
				placeholder="+91 98765 43210"
				:disabled="working"
			/>
		</div>

		<div class="cloud-settings-help-container">
			<p v-if="message" class="cloud-settings-help">{{ message }}</p>
			<p v-else class="cloud-settings-help">
				<svg class="icon icon-xs"><use href="#icon-lock"></use></svg>
				{{ __("The gateway collects your card securely - this site never sees it.") }}
			</p>
		</div>

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
			<button
				v-if="checkout"
				class="btn btn-sm btn-primary"
				:disabled="working"
				@click="check"
			>
				{{ __("Check status") }}
			</button>
			<button v-else class="btn btn-sm btn-primary" :disabled="!canContinue" @click="start">
				{{ continueLabel }}
			</button>
		</div>
	</div>
</template>
