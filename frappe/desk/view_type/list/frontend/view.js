// The List type's renderer is today's list body, until the list page and its renderers split (#46029).
export default {
	renderer: () => import("@/pages/list/DoctypeList.vue"),
};
