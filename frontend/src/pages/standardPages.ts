// The framework's own pages: the default registration for each address no app replaces.

import type { StandardPages } from "@/contributions/types";
import MainPage from "@/pages/MainPage.vue";

export const standardPages: StandardPages = {
	main: MainPage,
	home: () => import("@/pages/Home.vue"),
	module: () => import("@/pages/Module.vue"),
	list: () => import("@/pages/List.vue"),
	record: () => import("@/pages/Record.vue"),
	newRecord: () => import("@/pages/NewRecord.vue"),
};
