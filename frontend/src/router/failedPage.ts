// The address a navigation failed to open; the shell shows its error page until one lands.
import { ref } from "vue";
import { isNavigationFailure, NavigationFailureType, type Router } from "vue-router";

export const failedPage = ref<string | null>(null);

/** Records the address a navigation fails to open, and forgets it once a navigation lands. */
export function trackFailedPages(router: Router) {
	router.onError((error, to) => {
		console.error(error);
		failedPage.value = router.resolve(to).href;
	});
	router.afterEach((_to, _from, failure) => {
		// A duplicate lands on the page already shown, which clears the error too.
		if (!failure || isNavigationFailure(failure, NavigationFailureType.duplicated))
			failedPage.value = null;
	});
}
