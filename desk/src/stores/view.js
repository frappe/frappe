import { createResource } from "frappe-ui"
import { ref, computed } from "vue"
import { isEqual } from "lodash"

const doctype = ref("")
const configName = ref("")
const isDefaultConfig = ref(true)
const isDefaultOverriden = ref(false)
const listConfig = ref({})
const oldConfig = ref({})
const configUpdated = computed(() => !isEqual(listConfig.value, oldConfig.value))
const doctypeSavedViews = ref([])

const configSettings = createResource({
	url: "frappe.desk.doctype.view_config.view_config.get_config",
	makeParams() {
		return {
			doctype: doctype.value,
			config_name: configName.value,
			is_default: isDefaultConfig.value,
		}
	},
	onSuccess(data) {
		isDefaultOverriden.value = !data.from_meta
		configName.value = data.name
		doctypeSavedViews.value = configSettings.data.views
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
