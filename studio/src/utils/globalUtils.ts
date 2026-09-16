import { h } from "vue"
import { toast, call } from "frappe-ui"
import { Icon } from "frappe-ui/experimental"

function getIcon(name: string) {
	return h(Icon, { name })
}

export { getIcon, toast, call }