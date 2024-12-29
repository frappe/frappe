<template>
	<div
		class="relative flex h-full flex-col justify-between transition-all duration-300 ease-in-out w-[220px]"
	>
		<div>
			<UserDropdown class="p-2" />
		</div>
		<div class="flex-1 overflow-y-auto">
			<nav class="mb-3 flex flex-col">
				<SidebarLink
					class="mx-2 my-0.5"
					:label="previousRoute ? 'Back to app' : 'Back'"
					icon="arrow-left"
					:noExternalLinkIcon="true"
					@click="goBack"
				/>
				<SidebarLink
					class="mx-2 my-0.5"
					v-for="link in links"
					:icon="link.icon"
					:label="link.label"
					:to="link.to"
					@click="link.onClick"
				/>
			</nav>
		</div>
	</div>
</template>
<script setup>
import UserDropdown from '@/components/UserDropdown.vue'
import BillingIcon from '@/icons/BillingIcon.vue'
import CardIcon from '@/icons/CardIcon.vue'
import Plans from '@/icons/PlansIcon.vue'
import InvoiceIcon from '@/icons/InvoiceIcon.vue'
import SidebarLink from '@/components/SidebarLink.vue'
import { createDialog } from '../dialogs'
import { call } from 'frappe-ui'
import { useRouter } from 'vue-router'
import { useStorage } from '@vueuse/core'
import { onMounted, inject } from 'vue'

const router = useRouter()
const previousRoute = useStorage('previousRoute', null)

const team = inject('team')
const currentSiteInfo = inject('currentSiteInfo')

onMounted(() => {
	if (document.referrer) {
		previousRoute.value = document.referrer
	}
})

const links = [
	{
		label: 'Overview',
		icon: BillingIcon,
		to: 'Overview',
	},
	{
		label: 'Plans',
		icon: Plans,
		to: 'Plans',
	},
	{
		label: 'Invoices',
		icon: InvoiceIcon,
		to: 'Invoices',
	},
	{
		label: 'Cards',
		icon: CardIcon,
		to: 'Cards',
	},
	{
		label: 'Support',
		icon: 'life-buoy',
		onClick: () => openSupport(),
	},
]

function goBack() {
	if (previousRoute.value) {
		window.location.href = previousRoute.value
	} else {
		router.go(-1)
	}
}

async function openSupport() {
	await currentSiteInfo.reload()
	if (!currentSiteInfo.data?.plan?.support_included) {
		let supportPlan = await call(
			'frappe.integrations.frappe_providers.frappecloud_billing.api',
			{
				method: 'site.get_first_support_plan',
			}
		)
		if (!supportPlan) return
		let currency = team.data.currency == 'INR' ? '₹' : '$'
		let price = currency === '₹' ? supportPlan.price_inr : supportPlan.price_usd
		createDialog({
			title: `Upgrade to ${currency}${price}/mo Plan`,
			message: `Please upgrade to the ${currency}${price}/mo plan to get support`,
			actions: [
				{
					label: 'Upgrade',
					variant: 'solid',
					onClick: (close) => {
						router.push({ name: 'Plans' })
						close()
					},
				},
			],
		})
		return
	}
	window.open('https://support.frappe.io/help', '_blank')
}
</script>
