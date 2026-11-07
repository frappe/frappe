<script>
import { studioApps } from "@/data/studioApps"

// intermediate component to find and redirect to the app home when someone lands on the app
export default {
	name: "StudioApp",
	async beforeRouteEnter(to, _, next) {
		if (to.params.pageID) {
			next()
		} else {
			const appID = to.params.appID
			const app = await studioApps.fetchOne.submit(appID)
			const app_home = app?.[0]?.app_home
			if (app_home) {
				next({
					name: "StudioPage",
					params: { appID: appID, pageID: app_home },
				})
			} else {
				next({
					name: "StudioPage",
					params: { appID: appID, pageID: "new" },
				})
			}
		}
	},
}
</script>
