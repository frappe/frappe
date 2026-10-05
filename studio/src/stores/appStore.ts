import { defineStore } from "pinia"
import { ref, computed } from "vue"
import { useRouter } from "vue-router"

import useCodeStore from "@/stores/codeStore"

import type { StudioPage } from "@/types/Studio/StudioPage"
import type { PageScope } from "@/stores/pageScope"

const useAppStore = defineStore("appStore", () => {
	const activePage = ref<StudioPage | null>(null)

	const router = useRouter()
	const routeObject = computed(() => router.currentRoute.value)
	const codeStore = useCodeStore()
	codeStore.setRouteObject(routeObject)
	codeStore.setRouterObject(router)

	async function setPageData(page: StudioPage, scope: PageScope) {
		activePage.value = page
		await scope.setPageVariables(page, page.variables)
		await scope.setPageResources(page, false, page.resources)
	}

	return {
		setPageData,
		activePage,
		routeObject,
	}
})

export default useAppStore
