<template>
	<Dropdown :options="dropdownOptions" v-bind="$attrs">
		<template v-slot="{ open }">
			<button
				class="flex h-12 items-center rounded-md py-2 duration-300 ease-in-out w-52 px-2"
				:class="open ? 'bg-white shadow-sm' : 'hover:bg-gray-200'"
			>
				<FCLogo class="size-8 flex-shrink-0 rounded" />
				<div class="flex flex-1 flex-col text-left duration-300 ease-in-out ml-2 w-auto">
					<div class="text-base font-medium leading-none text-gray-900">
						{{ 'Frappe Cloud' }}
					</div>
					<div class="mt-1 text-sm leading-none text-gray-700">
						{{ user?.fullName }}
					</div>
				</div>
				<div class="duration-300 ease-in-out ml-2 w-auto">
					<FeatherIcon
						name="chevron-down"
						class="size-4 text-gray-600"
						aria-hidden="true"
					/>
				</div>
			</button>
		</template>
	</Dropdown>
</template>

<script setup>
import FCLogo from '@/logo/FCLogo.vue'
import Apps from '@/components/Apps.vue'
import { getSession } from '@/session.js'
import { Dropdown, FeatherIcon } from 'frappe-ui'
import { computed, ref, markRaw } from 'vue'

const { user, logout } = getSession()

let dropdownOptions = ref([
	{
		group: 'Apps',
		hideLabel: true,
		items: [
			{
				component: markRaw(Apps),
			},
		],
	},
	{
		group: 'Manage',
		hideLabel: true,
		items: [
			{
				icon: 'monitor',
				label: computed(() => 'Frappe Cloud Dashboard'),
				onClick: () => window.open('https://frappecloud.com/dashboard', '_blank'),
			},
			{
				icon: 'book-open',
				label: computed(() => 'About Us'),
				onClick: () => window.open('https://frappe.io', '_blank'),
			},
			{
				icon: 'phone',
				label: computed(() => 'Contact Us'),
				onClick: () => window.open('https://frappe.io/contact-us', '_blank'),
			},
		],
	},
	{
		group: 'Others',
		hideLabel: true,
		items: [
			{
				icon: 'log-out',
				label: computed(() => 'Log out'),
				onClick: () => logout.submit(),
			},
		],
	},
])
</script>
