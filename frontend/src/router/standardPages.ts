// The page each main address opens when no app declared one in its place.

export const standardPages = {
	list: () => import("@/pages/List.vue"),
	record: () => import("@/pages/Record.vue"),
};
