import { h } from "vue"
import { toast } from "frappe-ui"
import { Icon } from "frappe-ui/icons"

function getIcon(name: string) {
	return h(Icon, { name })
}

export { getIcon, toast }