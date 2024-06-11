import { createResource } from "frappe-ui"
import { ref } from "vue"

export const doctype = ref("")
export const config_name = ref("")
export const isDefaultConfig = ref(true)
export const isDefaultOverriden = ref(false)

export const config_settings = createResource({
	url: "frappe.desk.doctype.view_config.view_config.get_config",
	makeParams() {
		return {
			doctype: doctype.value,
			config_name: config_name.value,
			is_default: isDefaultConfig.value,
		}
	},
	onSuccess(response) {
		isDefaultOverriden.value = !response.from_meta
		config_name.value = response.name
	},
})
