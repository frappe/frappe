// The framework's own pages: the default registration for each address no app replaces.

import type { StandardPages } from "@/contributions/types";
import MainPage from "@/pages/MainPage.vue";
import IndexSkeleton from "@/pages/index/IndexSkeleton.vue";
import { loadedPage } from "@/router/mainPage";

export const standardPages: StandardPages = {
	main: MainPage,
	list: () => import("@/pages/List.vue"),
	record: () => import("@/pages/Record.vue"),
	newRecord: () => import("@/pages/NewRecord.vue"),
	index: loadedPage(() => import("@/pages/index/IndexPage.vue"), IndexSkeleton),
};
