import { defineStore } from "pinia"
import { ref, shallowRef, type ComputedRef } from "vue"
import type { Router } from "vue-router"
import { setPageScriptHotUpdateHandler } from "@/data/studioPageScripts"
import { createPageScope } from "@/stores/pageScope"

const useCodeStore = defineStore("codeStore", () => {
	const routeObject = ref<ComputedRef>()
	const routerObject = ref<Router | Readonly<Router>>()
	const activeScope = shallowRef(createPageScope(routeObject, routerObject))

	setPageScriptHotUpdateHandler((pageName, setup) => activeScope.value.applyPageScriptHotUpdate(pageName, setup))

	return {
		setRouteObject: (route: ComputedRef) => (routeObject.value = route),
		setRouterObject: (router: Router | Readonly<Router>) => (routerObject.value = router),
		routeObject,
		routerObject,
		activeScope,
	}
})

export function usePageScope() {
	return useCodeStore().activeScope
}

export default useCodeStore
