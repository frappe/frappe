import { h } from "vue"
import { Icon } from "frappe-ui/icons"

function getIcon(name: string) {
	return h(Icon, { name })
}

export { getIcon }