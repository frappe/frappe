import { defineStore } from "pinia"
import { ref, shallowRef, inject, getCurrentInstance, type ComputedRef, type InjectionKey } from "vue"
import type { Router } from "vue-router"
import { onPageScriptHotUpdate } from "@/data/studioPageScripts"
import { createPageScope, type PageScope } from "@/page/pageScope"

// The editor's page scope. Rendered apps give each page its own (see AppPage.vue).
const useCodeStore = defineStore("codeStore", () => {
	const routeObject = ref<ComputedRef>()
	const routerObject = ref<Router | Readonly<Router>>()
	const pageScope = shallowRef(createPageScope(routeObject, routerObject))

	onPageScriptHotUpdate((pageName, setup) => pageScope.value.applyPageScriptHotUpdate(pageName, setup))

	return {
		setRouteObject: (route: ComputedRef) => (routeObject.value = route),
		setRouterObject: (router: Router | Readonly<Router>) => (routerObject.value = router),
		routeObject,
		routerObject,
		pageScope,
	}
})

export const pageScopeKey: InjectionKey<PageScope> = Symbol("pageScope")

export function usePageScope(): PageScope {
	// inject() warns outside a component; stores and tests call this from plain functions
	const provided = getCurrentInstance() ? inject(pageScopeKey, null) : null
	return provided ?? useCodeStore().pageScope
}

export default useCodeStore
