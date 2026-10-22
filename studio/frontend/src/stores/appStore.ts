import { defineStore } from "pinia"
import { ref, computed } from "vue"
import { useRouter } from "vue-router"

import useCodeStore from "@/stores/codeStore"

import type { StudioPage } from "@/types/Studio/StudioPage"

const useAppStore = defineStore("appStore", () => {
	const activePage = ref<StudioPage | null>(null)

	const router = useRouter()
	const routeObject = computed(() => router.currentRoute.value)
	const codeStore = useCodeStore()
	codeStore.setRouteObject(routeObject)
	codeStore.setRouterObject(router)

	return {
		activePage,
		routeObject,
	}
})

export default useAppStore
