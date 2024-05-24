<template>
    <div v-if="list.data">
        <ListView v-model="list_config" :options="{
        showTooltip: false,
        resizeColumn: true,
        showColumnSettings: true,
        showFilters: true,
        emptyState: {
            title: 'No records found',
            description: 'Create a new record to get started',
            button: {
                label: `New ${route.params.doctype}`,
                onClick: () => {
                    //add route to create new record
                }
            },
        },
    }" @update="handleUpdateConfig" @filterChange="handleFilterChange">
            <template #customControls>
                <div class="flex items-center gap-2">
                    <Dropdown :placement="'right'" :options="viewsDropdownOptions">
                        <template #default="{ open }">
                            <Button :label="config_settings.data?.label">
                                <template #prefix>
                                    <FeatherIcon :name="config_settings.data?.icon || 'list'" class="h-3.5" />
                                </template>
                                <template #suffix>
                                    <FeatherIcon :name="open ? 'chevron-up' : 'chevron-down'"
                                        class="h-3.5 text-gray-600" />
                                </template>
                            </Button>
                        </template>
                    </Dropdown>
                </div>
            </template>
        </ListView>
    </div>
</template>

<script setup>
import { config_name, config_settings, isDefaultConfig } from '@/stores/view';
import { createResource, FeatherIcon, Dropdown, call } from 'frappe-ui';
import { ref, watch, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ListView from '@/components/ListView.vue';

const route = useRoute();
const router = useRouter();

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

const list_config = ref({});

const loadList = async (config) => {
    await list.fetch();
    list_config.value = {
        rows: list.data,
        rowKey: "name",
        columns: config.columns,
        fields: config.doctype_fields,
        filters: getParsedFilters(),
    };
}

const filters = computed(() => {
    if (route.query) {
        let filters = {};
        for (let key in route.query) {
            if (key == 'config')
                continue;
            filters[key] = JSON.parse(route.query[key]);
        }
        return filters;
    }
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

watch(() => route.query.config, async (query_config) => {
    if (!query_config) {
        isDefaultConfig.value = true;
        config_name.value = route.params.doctype;
    }
    else {
        isDefaultConfig.value = false;
        config_name.value = query_config;
    }
    await config_settings.fetch();
    loadList(config_settings.data);
}, { immediate: true });

const updateConfigResource = createResource({
    url: 'frappe.desk.doctype.view_config.view_config.update_config',
    method: 'POST',
});

const handleUpdateConfig = async (config) => {
    updateConfigResource.submit({ config_name: config_name.value, new_config: config });
    loadList(config);
};

// TODO: add default view routes
const defaultViews = [
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
];

const viewsDropdownOptions = computed(() => {
    let _views = [
        {
            group: 'Default Views',
            items: defaultViews,
        },
    ]

    let saved_views = [];
    if (config_settings.data?.document_type) {
        call('frappe.desk.doctype.view_config.view_config.get_views_for_doctype', {
            doctype: config_settings.data.document_type
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

            saved_views.length && _views.push({
                group: 'Saved Views',
                items: saved_views,
            });
        });
    }
    return _views;
});

const handleFilterChange = async (filter) => {
    router.replace({ query: { ...route.query, [filter.field]: JSON.stringify([filter.operator, filter.value]) } });
    await list.fetch();
    list_config.value.rows = list.data;
};

</script>