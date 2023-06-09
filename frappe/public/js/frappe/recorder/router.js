import { createWebHistory, createRouter } from "vue-router";
import RecorderDetail from "./RecorderDetail.vue";
import RequestDetail from "./RequestDetail.vue";

const routes = [
	{
		path: "/detail",
		name: "RecorderDetail",
		component: RecorderDetail,
	},
	{
		path: "/request/:id",
		name: "RequestDetail",
		component: RequestDetail,
		meta: { shouldFetch: true },
	},
	{
		path: "/",
		redirect: "/detail",
	},
];

const router = createRouter({
	history: createWebHistory("/app/recorder/"),
	routes,
});

export default router;
