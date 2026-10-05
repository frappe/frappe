import { defineStore } from "pinia"
import { ref, shallowRef, type ComputedRef } from "vue"
import type { Router } from "vue-router"
import { setPageScriptHotUpdateHandler } from "@/data/studioPageScripts"
import { createPageScope, type PageScope } from "@/stores/pageScope"

// The app renderer loads the next page into a new scope and activates it with the new blocks,
// so the page on screen keeps its data until then
const useCodeStore = defineStore("codeStore", () => {
	const routeObject = ref<ComputedRef>()
	const routerObject = ref<Router | Readonly<Router>>()
	const activeScope = shallowRef(newPageScope())

	function newPageScope(): PageScope {
		return createPageScope(routeObject, routerObject)
	}

	function activatePageScope(scope: PageScope) {
		activeScope.value = scope
	}

	setPageScriptHotUpdateHandler((pageName, setup) => activeScope.value.applyPageScriptHotUpdate(pageName, setup))

	return {
		setRouteObject: (route: ComputedRef) => (routeObject.value = route),
		setRouterObject: (router: Router | Readonly<Router>) => (routerObject.value = router),
		routeObject,
		routerObject,
		activeScope,
		createPageScope: newPageScope,
		activatePageScope,
	}
})

export function usePageScope() {
	return useCodeStore().activeScope
}

export default useCodeStore
