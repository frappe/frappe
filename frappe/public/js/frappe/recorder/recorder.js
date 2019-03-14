import Vue from 'vue/dist/vue.js';
import VueRouter from 'vue-router/dist/vue-router.js';

import RecorderRoot from "./RecorderRoot.vue";

import RecorderDetail from "./RecorderDetail.vue";
import RequestDetail from "./RequestDetail.vue";

Vue.use(VueRouter);
const routes = [
	{
		name: "recorder-detail",
		path: '/desk',
		component: RecorderDetail,
	},
	{
		name: "request-detail",
		path: '/request/:id',
		component: RequestDetail,
	},
];

const router = new VueRouter({
	mode: 'history',
	base: "/desk#recorder/",
	routes: routes,
});

new Vue({
	el: ".recorder-container",
	router: router,
	data: {
		page: cur_page.page.page
	},
	template: "<recorder-root/>",
	components: {
		RecorderRoot,
	}
});
