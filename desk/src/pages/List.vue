<template>
    <div class="m-6">
        <template v-if="list.data">
            <ListView :rows="list.data" :columns="config_settings.data.columns" rowKey="key" :options="{
            showTooltip: false,
            resizeColumn: true,
        }" />
        </template>
    </div>
</template>

<script setup>
import { config_name, config_settings } from '@/stores/view'
import { ListView } from 'frappe-ui';
import { createResource } from 'frappe-ui';
import { watch } from 'vue';
import { useRoute } from 'vue-router';

const route = useRoute();

const list = createResource({
    url: `frappe.client.get_list`,
    makeParams() {
        return {
            doctype: route.params.doctype,
            fields: config_settings.data?.columns.map(column => column.key),
            filters: [],
            limit: 20,
            start: 0,
            sort_by: 'creation',
            sort_order: 'desc',
        }
    }
});

watch(() => route.query.config, async (config) => {
    config_name.value = config;
    await config_settings.fetch();
    await list.fetch();
}, { immediate: true });

</script>