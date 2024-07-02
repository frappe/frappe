import { ref, computed } from "vue"
import { createResource } from "frappe-ui"
import { isEqual } from "lodash"

import { Resource } from "@/types/frappeUI"
import { ListConfiguration, SavedView } from "@/types/list"

const doctype = ref("")
const configName = ref("")
const isDefaultConfig = ref(true)
const isDefaultOverriden = ref(false)
const listConfig = ref<ListConfiguration>()

const oldConfig = ref<ListConfiguration>()
const configUpdated = computed(() => !isEqual(listConfig.value, oldConfig.value))
const doctypeSavedViews = ref<SavedView[]>()

type configSettingsResource = Omit<Resource, "data"> & { data: ListConfiguration }

const configSettings: configSettingsResource = createResource({
	url: "frappe.desk.doctype.view_config.view_config.get_config",
	makeParams() {
		return {
			doctype: doctype.value,
			config_name: configName.value,
			is_default: isDefaultConfig.value,
		}
	},
	onSuccess(data: ListConfiguration) {
		isDefaultOverriden.value = !data.from_meta
		configName.value = data.name
		doctypeSavedViews.value = data.views
	},
})

export {
	doctype,
	configName,
	configSettings,
	listConfig,
	oldConfig,
	configUpdated,
	isDefaultConfig,
	isDefaultOverriden,
	doctypeSavedViews,
}
