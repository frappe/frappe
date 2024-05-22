import { createResource } from 'frappe-ui';
import { ref } from 'vue';

export const config_name = ref('');
export const isDefaultConfig = ref(true);

export const config_settings = createResource({
    url: 'frappe.desk.doctype.view_config.view_config.get_config',
    makeParams() {
        return {
            config_name: config_name.value,
            is_default: isDefaultConfig.value
        }
    }
});