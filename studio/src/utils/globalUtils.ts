import { toast, call } from "frappe-ui"

// kept for page scripts and saved bindings written against the removed sprite icons
function getIcon(name: string) {
	return name.startsWith("lucide-") ? name : `lucide-${name}`
}

export { getIcon, toast, call }
