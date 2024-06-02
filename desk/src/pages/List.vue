<template>
    <template v-if="listConfig && list.data">
        <div class="flex flex-col h-[42rem] gap-4 my-4 mx-5">
            <div class="flex justify-between items-center">
                <div>
                </div>
                <div class="flex gap-2" v-if="config_settings.data">
                    <div class="flex gap-0">
                        <Dropdown :placement="'right'" :options="viewsDropdownOptions">
                            <template #default="{ open }">
                                <Button :class="configUpdated ? 'rounded-none rounded-l' : ''"
                                    :label="config_settings.data.label">
                                    <template #prefix>
                                        <FeatherIcon :name="config_settings.data.icon || 'list'"
                                            class="h-3.5 text-gray-600" />
                                    </template>
                                </Button>
                            </template>
                        </Dropdown>
                        <div v-if="configUpdated" class="flex items-center">
                            <Tooltip text="Discard Changes" :hover-delay="0.5">
                                <div>
                                    <Button class="rounded-none border-x border-gray-300" variant="subtle"
                                        @click="cancelChanges">
                                        <template #default>
                                            <FeatherIcon name="rotate-ccw" class="h-3"></FeatherIcon>
                                        </template>
                                    </Button>
                                </div>
                            </Tooltip>
                            <template v-if="isDefaultConfig">
                                <Tooltip text="Create View" :hover-delay="0.5">
                                    <div>
                                        <Button class="rounded-none rounded-r" variant="subtle"
                                            @click="viewModalMode = 'Create'; showViewActionsModal = true;">
                                            <template #default>
                                                <FeatherIcon name="save" class="h-3.5"></FeatherIcon>
                                            </template>
                                        </Button>
                                    </div>
                                </Tooltip>
                            </template>
                            <template v-else>
                                <Tooltip text="Save Changes" :hover-delay="0.5">
                                    <div>
                                        <Button class="rounded-none rounded-r" variant="subtle" @click="updateView()">
                                            <template #default>
                                                <FeatherIcon name="save" class="h-3.5"></FeatherIcon>
                                            </template>
                                        </Button>
                                    </div>
                                </Tooltip>
                            </template>
                        </div>
                    </div>
                    <template v-if="listConfig.fields">
                        <ListControls v-model="listConfig" :options="listControlOptions"
                            @update="handleUpdateControls" />
                    </template>
                </div>
            </div>
            <div v-if="list.data?.length">
                <ListView :rows="list.data" rowKey="name" :columns="listConfig.columns" :options="listOptions">
                    <template #cell="{ item, row, column }">
                        <template v-if="column.type === 'status'">
                            <Badge :variant="'solid'" theme="gray" size="md">
                                {{ item }}
                            </Badge>
                        </template>
                        <template v-else-if="column.type === 'Check'">
                            <Checkbox class="text-gray-800" size="sm" :model-value="Boolean(item)" :disabled="true" />
                        </template>
                        <template v-else>
                            <span class="text-base">{{ item }}</span>
                        </template>
                    </template>
                </ListView>
            </div>
        </div>
        <ListFooter class="border-t px-5 py-2" v-model="pageLength" :options="{
            rowCount: list.data.length,
            totalCount: totalCount,
        }" @loadMore="emit('loadMore')" />
        <ViewActionsModal v-model="showViewActionsModal" :mode="viewModalMode" :listConfig="listConfig" :queryFilters="queryFilters"/>
    </template>
</template>

<script setup>
import { config_name, config_settings, isDefaultConfig } from '@/stores/view';
import { call, createResource, FeatherIcon, Dropdown, Tooltip } from 'frappe-ui';
import { ref, computed, onBeforeMount, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { ListView, ListFooter, Badge, Checkbox } from 'frappe-ui';
import ListControls from '@/components/ListControls.vue';
import ViewActionsModal from '@/components/ViewActionsModal.vue';

const route = useRoute();
const router = useRouter();

const viewsDropdownOptions = computed(() => {
    let options = [];
    !isDefaultConfig.value && options.push({
        group: 'View Actions',
        items: [
            {
                label: 'Duplicate',
                icon: 'copy',
            },
            {
                label: 'Rename',
                icon: 'edit-3',
                onClick: () => {
                    viewModalMode.value = 'Save';
                    showViewActionsModal.value = true;
                }
            },
            {
                label: 'Delete',
                icon: 'trash',
                onClick: () => {
                    viewModalMode.value = 'Delete';
                    showViewActionsModal.value = true;
                }
            }
        ]
    });
    options.push({
        group: 'Default Views',
        items: [
            {
                label: 'List',
                icon: 'list',
                onClick: async () => {
                    await router.replace({ query: { view: null } });
                    router.go();
                }
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
    });
    let saved_views = [];
    if (route.params.doctype) {
        call('frappe.desk.doctype.view_config.view_config.get_views_for_doctype', {
            doctype: route.params.doctype
        }).then((res) => {
            res.map((v) => {
                v.name != config_name.value && saved_views.push({
                    label: v.label,
                    icon: v.icon,
                    onClick: async () => {
                        await router.replace({ query: { view: v.name } });
                        router.go();
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
    showSortSelector: true,
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

// Display list based on default or saved view

onBeforeMount(async () => {
    let query_config = route.query.view;
    await loadConfig(query_config);
    await addViewFiltersToQueryParams(query_config);
    await createConfigObj();
    await list.fetch();
    await castListFieldValues();
});

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
};

const addViewFiltersToQueryParams = async (query_config) => {
    if (query_config == null)
        return;
    let query_params = { view: query_config };
    config_settings.data.filters.map((f) => {
        let fieldname = f[0];
        if (query_params[fieldname])
            query_params[fieldname].push(JSON.stringify([f[1], f[2]]));
        else
            query_params[fieldname] = [JSON.stringify([f[1], f[2]])];
    });
    await router.push({ query: query_params });
}

const createConfigObj = async () => {
    listConfig.value = {
        columns: config_settings.data.columns,
        fields: config_settings.data.doctype_fields,
        filters: currentFilters.value,
        sort: [config_settings.data.sort_field || 'modified', config_settings.data.sort_order || 'DESC'],
    };
    oldConfig.value = JSON.parse(JSON.stringify(listConfig.value));
}

const list = createResource({
    url: `frappe.client.get_list`,
    makeParams() {
        return {
            doctype: route.params.doctype,
            fields: listConfig.value.columns?.map((col) => col.key),
            filters: queryFilters.value,
            limit: pageLength.value,
            start: 0,
            order_by: querySort.value,
        }
    }
});

// Maintain current sort and filtering

const currentSort = computed(() => [listConfig.value.sort[0] || 'modified', listConfig.value.sort[1] || 'DESC']);

const querySort = computed(() => `${currentSort.value.join(' ')}`);

const getFieldType = (fieldname) => {
    return config_settings.data.doctype_fields.find((f) => f.value === fieldname).type || '';
};

const getSelectOptions = (fieldname) => {
    return config_settings.data.doctype_fields.find((f) => f.value === fieldname).options?.split("\n") || [];
};

const getParsedFilter = (key, filter) => {
    let f = JSON.parse(filter);
    return {
        fieldname: key,
        fieldtype: getFieldType(key),
        operator: f[0],
        value: f[1],
        options: getSelectOptions(key),
    };
};

const currentFilters = computed(() => {
    let temp = [];
    if (route.query) {
        for (let key in route.query) {
            if (key == 'view')
                continue;

            if (typeof (route.query[key]) == 'string')
                temp.push(getParsedFilter(key, route.query[key]));
            else {
                route.query[key].forEach((v) => {
                    temp.push(getParsedFilter(key, v));
                });
            }
        }
    }
    return temp;
});

const queryFilters = computed(() => currentFilters.value.map((f) => [f.fieldname, f.operator, f.value]) || []);

// Refresh list - on update of sort, columns, filters

const handleUpdateControls = async () => {
    await list.fetch();
}

// View Actions 

const cancelChanges = async () => {
    router.push({ query: { view: route.query.view } });
    await loadConfig(route.query.view);
    await list.fetch();
}

const updateView = async () => {
    call('frappe.desk.doctype.view_config.view_config.update_config',
        {
            config_name: config_name.value,
            new_config: {
                columns: listConfig.value.columns,
                doctype_fields: listConfig.value.fields,
                filters: queryFilters.value,
                sort: listConfig.value.sort,
            },
        }).then(() => {
            oldConfig.value = JSON.parse(JSON.stringify(listConfig.value));
        });
}

const showViewActionsModal = ref(false);
const viewModalMode = ref('');

const castListFieldValues = async () => {
    list.data?.map(async (row) => {
        for (let fieldname in row) {
            let fieldtype = getFieldType(fieldname);
            if (fieldtype === 'Link' && row[fieldname]) {
                let dt = getSelectOptions(fieldname)[0];
                let new_value = await call('frappe.desk.doctype.view_config.view_config.get_link_title_field', {
                    doctype: dt,
                    name: row[fieldname],
                });
                row[fieldname] = String(new_value);
            }
            else if (fieldtype === 'Datetime' && row[fieldname] && ['modified', 'creation'].includes(fieldname)) {
                row[fieldname] = new Date(row[fieldname]).toUTCString();
            }
        }
    });
}

const pageLength = ref(50);
const totalCount = ref();
const getTotalCount = async() => {
    return await call('frappe.client.get_count', {
        doctype: route.params.doctype,
        filters: queryFilters.value,
    });   
}

watch(list, async () => {
    castListFieldValues();
    totalCount.value = await getTotalCount();
});
</script>