// The address a navigation failed to open; the shell shows its error page until one lands.
import { readonly, ref } from "vue";
import {
	isNavigationFailure,
	NavigationFailureType,
	type RouteLocationNormalized,
	type Router,
} from "vue-router";

const failed = ref<string | null>(null);

export const failedPage = readonly(failed);

/** Records the address a navigation fails to open, and forgets it once a navigation lands. */
export function trackFailedPages(router: Router) {
	let latest: RouteLocationNormalized | null = null;
	router.beforeEach((to) => {
		latest = to;
	});
	router.onError((error, to) => {
		console.error(error);
		// A navigation abandoned for a newer one can still fail; the newer one owns the page.
		if (to !== latest) return;
		// The full path keeps a name's percent-encoding, which a resolve from params drops.
		failed.value = router.options.history.createHref(to.fullPath);
	});
	router.afterEach((_to, _from, failure) => {
		// A duplicate lands on the page already shown, which clears the error too.
		if (!failure || isNavigationFailure(failure, NavigationFailureType.duplicated))
			failed.value = null;
	});
}

/** Forgets the failed address; for tests. */
export function resetFailedPage() {
	failed.value = null;
}
