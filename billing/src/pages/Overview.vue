<template>
	<header class="flex h-10.5 border-b items-center justify-between py-2 px-5 shrink-0">
		<Breadcrumbs :items="[{ label: 'Billing Overview' }]" />
	</header>
	<div v-if="team.data" class="flex flex-1 flex-col px-60 pt-6 gap-8 overflow-y-auto">
		<CurrentPlan @changePlan="router.push({ name: 'Plans' })" />
		<PaymentDetails />
	</div>
	<div v-else class="flex flex-1 items-center justify-center">
		<Spinner class="size-8" />
	</div>
</template>
<script setup>
import CurrentPlan from '@/components/CurrentPlan.vue'
import PaymentDetails from '@/components/PaymentDetails.vue'
import { Spinner, createResource, Breadcrumbs } from 'frappe-ui'
import { useRouter } from 'vue-router'
import { computed, provide, inject } from 'vue'

const router = useRouter()

const team = inject('team')

const upcomingInvoice = createResource({
	url: 'frappe.integrations.frappe_providers.frappecloud_billing.api',
	params: { method: 'billing.upcoming_invoice' },
	cache: 'upcomingInvoice',
	auto: true,
})

provide('billing', {
	upcomingInvoice,
	availableCredits: computed(() => upcomingInvoice.data?.available_credits),
	currentBillingAmount: computed(() => upcomingInvoice.data?.upcoming_invoice?.total),
})
</script>
