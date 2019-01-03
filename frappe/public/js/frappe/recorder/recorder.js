import Vue from 'vue/dist/vue.js'
import VueRouter from 'vue-router/dist/vue-router.js'

import RecorderRoot from "./RecorderRoot.vue"

import RecorderDetail from "./RecorderDetail.vue"
import RequestDetail from "./RequestDetail.vue"
import SQLDetail from "./SQLDetail.vue"

frappe.ready(function() {
	Vue.use(VueRouter)
	const routes = [
		{
			name: "recorder-detail",
			path: '/',
			component: RecorderDetail,
		},
		{
			name: "request-detail",
			path: '/request/:request_uuid',
			component: RequestDetail,
		},
		{
			name: "sql-detail",
			path: '/request/:request_uuid/sql/:call_index',
			component: SQLDetail,
		},
	  ]

	const router = new VueRouter({
		mode: 'history',
		base: "/recorder",
		routes: routes,
	})

	new Vue({
		el: "#recorder",
		router: router,
		template: "<recorder-root/>",
		components: {
			RecorderRoot,
		}
	})
})
