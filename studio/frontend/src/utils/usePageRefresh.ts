import { ref } from "vue"
import { useRouter } from "vue-router"
import { reloadCurrentPage } from "@/page/pageLoader"

/**
 * Re-read the open page and remount it. The loader leaves the fresh definition for the next
 * mount, and the revision — keyed on in the renderer — is what remounts the page to pick it up.
 * Callers that changed the page on the server use this instead of reloading the whole app.
 */
export function usePageRefresh() {
	const router = useRouter()
	const revision = ref(0)

	async function refreshPage() {
		await reloadCurrentPage(router)
		revision.value++
	}

	return { revision, refreshPage }
}
