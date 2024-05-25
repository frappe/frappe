<template>
    <div class="flex flex-col gap-5 m-5">
        <div class="flex justify-between items-center">
            <div>
            </div>
            <div class="flex gap-4" v-if="config_settings.data">
                <Dropdown :placement="'right'" :options="viewsDropdownOptions">
                    <template #default="{ open }">
                        <Button :label="config_settings.data.label">
                            <template #prefix>
                                <FeatherIcon :name="config_settings.data.icon || 'list'" class="h-3.5 text-gray-600" />
                            </template>
                            <template #suffix>
                                <FeatherIcon :name="open ? 'chevron-up' : 'chevron-down'" class="h-3.5 text-gray-600" />
                            </template>
                        </Button>
                    </template>
                </Dropdown>
                <div v-if="configUpdated" class="flex items-center gap-2 border-r pr-2">
                    <Button :label="'Cancel'" @click="cancelChanges" />
                    <template v-if="isDefaultConfig">
                        <Button :label="'Create View'" />
                    </template>
                    <template v-else>
                        <Button :label="'Save'" @click="saveChangesToView" />
                    </template>
                </div>
                <ListControls v-model="listConfig" :options="listControlOptions" @updateFilter="handleFilterChange"/>
            </div>
        </div>
        <div v-if="list.data">
            <ListView :rows="list.data" rowKey="name" :columns="listConfig.columns" :options="listOptions" />
        </div>
    </div>
</template>

<script setup>
import { config_name, config_settings, isDefaultConfig } from '@/stores/view';
import { createResource, FeatherIcon, Dropdown, call } from 'frappe-ui';
import { ref, watch, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { ListView } from 'frappe-ui';
import ListControls from '@/components/ListControls.vue';

const route = useRoute();
const router = useRouter();

const viewsDropdownOptions = computed(() => {
    let options = [
        {
            group: 'Default Views',
            items: [
                {
                    label: 'List',
                    icon: 'list'
                },
                {
                    label: 'Report',
                    icon: 'table'
                },
                {
                    label: 'Kanban',
                    icon: 'grid'
                },
                {
                    label: 'Dashboard',
                    icon: 'pie-chart'
                }
            ]
        }
    ];
    let saved_views = [];
    if (route.params.doctype) {
        call('frappe.desk.doctype.view_config.view_config.get_views_for_doctype', {
            doctype: route.params.doctype
        }).then((res) => {
            res.map((v) => {
                v.name != config_name.value && saved_views.push({
                    label: v.label,
                    icon: v.icon,
                    onClick: () => {
                        router.push({ query: { config: v.name } });
                    }
                });
            });

            saved_views.length && options.push({
                group: 'Saved Views',
                items: saved_views,
            });
        });
    }
    return options;
});

const listControlOptions = {
    showColumnSettings: true,
    showFilters: true,
};

const listOptions = {
    showTooltip: false,
    selectable: true,
    resizeColumn: true,
    rowHeight: 40,
};

const listConfig = ref({});

const oldConfig = ref({});

const configUpdated = computed(() => JSON.stringify(oldConfig.value) != JSON.stringify(listConfig.value));

const loadConfig = async (query_config) => {
    if (!query_config) {
        isDefaultConfig.value = true;
        config_name.value = route.params.doctype;
    }
    else {
        isDefaultConfig.value = false;
        config_name.value = query_config;
    }
    await config_settings.fetch();
    listConfig.value = {
        columns: config_settings.data.columns,
        fields: config_settings.data.doctype_fields,
        filters: getParsedFilters(),
    };
    oldConfig.value = JSON.parse(JSON.stringify(listConfig.value));
};

const list = createResource({
    url: `frappe.client.get_list`,
    makeParams() {
        return {
            doctype: route.params.doctype,
            fields: ['*'],
            filters: filters.value,
            limit: 20,
            start: 0,
            sort_by: 'creation',
            sort_order: 'desc',
        }
    }
});

watch(() => route.query.config, async (query_config) => {
    await loadConfig(query_config);
    await list.fetch();
}, { immediate: true });

const updateConfigResource = createResource({
    url: 'frappe.desk.doctype.view_config.view_config.update_config',
    method: 'POST',
});

const saveChangesToView = () => {
    updateConfigResource.submit({ config_name: config_name.value, new_config: listConfig.value });
    loadList(config);
}

const cancelChanges = () => {
    listConfig.value = JSON.parse(JSON.stringify(oldConfig.value));
}

// Handle filters from URL query params

const filters = computed(() => {
    let filters = {};
    if (route.query) {
        for (let key in route.query) {
            if (key == 'config')
                continue;
            filters[key] = JSON.parse(route.query[key]);
        }
    }
    if (filters.length)
        return filters;
    // show config filters if no query params
    return config_settings.data.filters;
});

const getParsedFilters = () => {
    let parsedFilters = [];
    filters.value && Object.entries(filters.value).map(([field, filter]) => {
        parsedFilters.push({
            field: field,
            operator: filter[0],
            value: filter[1]
        });
    });
    return parsedFilters;
}

const handleFilterChange = async (filter) => {
    router.replace({ query: { ...route.query, [filter.field]: JSON.stringify([filter.operator, filter.value]) } });
    await list.fetch();
};

</script>