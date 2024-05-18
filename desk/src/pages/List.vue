<template>
    <div v-if="list.data">
        <ListView v-model="list_config" :options="{
        showTooltip: false,
        resizeColumn: true,
        showColumnSettings: true,
    }" @update="handleUpdateConfig" />
    </div>
</template>

<script setup>
import { config_name, config_settings } from '@/stores/view';
import { createResource } from 'frappe-ui';
import { ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import ListView from '@/components/ListView.vue';

const route = useRoute();

const list = createResource({
    url: `frappe.client.get_list`,
    makeParams() {
        return {
            doctype: route.params.doctype,
            fields: ['*'],
            filters: [],
            limit: 20,
            start: 0,
            sort_by: 'creation',
            sort_order: 'desc',
        }
    }
});

const list_config = ref({});

const loadList = async() => {
    await config_settings.fetch();
    await list.fetch();
    list_config.value = { rows: list.data, rowKey: "name", columns: config_settings.data.columns, allColumns: config_settings.data.doctype_fields };
}

watch(() => route.query.config, (query_config) => {
    config_name.value = query_config;
    loadList();
}, { immediate: true });

const updateConfigResource = createResource({
    url: 'frappe.desk.doctype.view_config.view_config.update_config',
    method: 'POST',
});

const handleUpdateConfig = async(config) => {
    updateConfigResource.submit({ config_name: config_name.value, new_config: config });
};

</script>