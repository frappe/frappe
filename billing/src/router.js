import { createRouter, createWebHistory } from 'vue-router'

const routes = [
	{
		path: '/',
		name: 'Overview',
		component: () => import('./pages/Overview.vue'),
	},
	{
		path: '/plans',
		name: 'Plans',
		component: () => import('./pages/Plans.vue'),
	},
	{
		path: '/invoices',
		name: 'Invoices',
		component: () => import('./pages/Invoices.vue'),
	},
	{
		path: '/cards',
		name: 'Cards',
		component: () => import('./pages/Cards.vue'),
	},
]

let router = createRouter({
	history: createWebHistory('/billing'),
	routes,
})

export default router
