<script>
import { sidebar } from "@/data/desktop"
import { getRoute } from "@/utils/routing"

export default {
	name: "Module",
	async beforeRouteEnter(to, _, next) {
		if (to.params.workspace) {
			next()
		} else {
			const module = to.params.module
			await sidebar.submit({ module: module })

			const moduleHome = getRoute(sidebar.data.module_home, module)
			next(moduleHome)
		}
	},
}
</script>
