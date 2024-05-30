<template>
    <div class="flex flex-col h-[41.5rem] gap-4 my-4 mx-5">
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
                            <Button class="rounded-none border-x border-gray-300" variant="subtle"
                                @click="cancelChanges">
                                <template #default>
                                    <FeatherIcon name="rotate-ccw" class="h-3"></FeatherIcon>
                                </template>
                            </Button>
                        </Tooltip>
                        <template v-if="isDefaultConfig">
                            <Tooltip text="Create View" :hover-delay="0.5">
                                <Button class="rounded-none rounded-r" variant="subtle" @click="modalMode = 'Create' ; showModal = true;">
                                    <template #default>
                                        <FeatherIcon name="save" class="h-3.5"></FeatherIcon>
                                    </template>
                                </Button>
                            </Tooltip>
                        </template>
                        <template v-else>
                            <Tooltip text="Save Changes" :hover-delay="0.5">
                                <Button class="rounded-none rounded-r" variant="subtle" @click="updateView()">
                                    <template #default>
                                        <FeatherIcon name="save" class="h-3.5"></FeatherIcon>
                                    </template>
                                </Button>
                            </Tooltip>
                        </template>

                    </div>
                </div>
                <ListControls v-model="listConfig" :options="listControlOptions" @updateFilter="handleFilterChange" />
            </div>
        </div>
        <div v-if="list.data?.length">
            <ListView :rows="list.data" rowKey="name" :columns="listConfig.columns" :options="listOptions" />
        </div>
    </div>
    <Dialog v-model="showModal" :options="{
                title: ` ${ modalMode } View `,
                actions: [
                    {
                        label: modalMode,
                        variant: 'solid',
                        onClick: () => {
                            if (modalMode == 'Create')
                                createView()
                            else if (modalMode == 'Save')
                                renameView()
                            else
                                deleteView()
                        },
                    },
                ],
                size: 'sm'
            }">
        <template #body-content>
            <template v-if="modalMode == 'Create'">
                <FormControl :type="'text'" size="md" variant="subtle" label="View Name" v-model="newViewName" />
            </template>
            <template v-else-if="modalMode == 'Save'">
                <FormControl :type="'text'" size="md" variant="subtle" label="View Name"
                    v-model="config_settings.data.label" />
            </template>
            <template v-else>
                <div class="text-base">
                    Are you sure you want to delete this view?
                </div>
            </template>
        </template>
    </Dialog>
</template>

<script setup>

import { config_name, config_settings, isDefaultConfig } from '@/stores/view';
import { createResource, FeatherIcon, Dropdown, call, Tooltip, Dialog, FormControl } from 'frappe-ui';
import { ref, watch, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { ListView } from 'frappe-ui';
import ListControls from '@/components/ListControls.vue';

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
                    modalMode.value = 'Save';
                    showModal.value = true;
                }
            },
            {
                label: 'Delete',
                icon: 'trash',
                onClick: () => {
                    modalMode.value = 'Delete';
                    showModal.value = true;
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
                onClick: () => {
                    router.push({ query: { view: null } });
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
                    onClick: () => {
                        router.push({ query: { view: v.name } });
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
        filters: filters.value,
        sort: [config_settings.data.sort_field, config_settings.data.sort_order],
    };
    oldConfig.value = JSON.parse(JSON.stringify(listConfig.value));
};

const sort = computed(() => {
    if (!listConfig.value.sort) 
        return 'modified DESC';
    return  `${listConfig.value.sort[0]} ${listConfig.value.sort[1]}`;
});

const list = createResource({
    url: `frappe.client.get_list`,
    makeParams() {
        return {
            doctype: route.params.doctype,
            fields: listConfig.value.columns?.map((col) => col.key),
            filters: listConfig.value.filters,
            limit: 20,
            start: 0,
            order_by: sort.value,
        }
    }
});

watch(() => route.query.view, async (query_config) => {
    await loadConfig(query_config);
}, { immediate: true });

watch(() => listConfig.value, async () => {
    await list.fetch();
}, { deep: true, immediate: true });

const createConfigResource = createResource({
    url: 'frappe.client.insert',
    method: 'POST',
    makeParams: () => {
        return {
            doc: {
                doctype: 'View Config',
                document_type: route.params.doctype,
                columns: JSON.stringify(listConfig.value.columns),
                filters: JSON.stringify(listConfig.value.filters),
                label: newViewName.value,
            }
        }
    }
});

const updateConfigResource = createResource({
    url: 'frappe.desk.doctype.view_config.view_config.update_config',
    method: 'POST',
});

const showModal = ref(false);
const modalMode = ref('');
const newViewName = ref('');

const createView = async () => {
    showModal.value = false;
    let doc = await createConfigResource.submit();
    router.push({ query: { view: doc.name } });
    await loadConfig(doc.name);
    await list.fetch();
}

const updateView = async () => {
    await updateConfigResource.submit({ config_name: config_name.value, new_config: listConfig.value });
    await list.fetch();
}

const deleteView = async () => {
    await call('frappe.client.delete', { doctype: "View Config", name: config_name.value });
    showModal.value = false;
    router.replace({ query: {} });
}

const renameView = async () => {
    showModal.value = false;
    await call('frappe.client.set_value', {
        doctype: "View Config",
        name: config_name.value,
        fieldname: "label",
        value: config_settings.data.label
    });
}

const cancelChanges = () => {
    listConfig.value = JSON.parse(JSON.stringify(oldConfig.value));
}

// Handle filters from URL query params

const getParsedFilter = (key, filter) => {
    let f = JSON.parse(filter);
    return [key, f[0], f[1]];
}

const filters = computed(() => {
    let filters = [];
    if (route.query) {
        for (let key in route.query) {
            if (key == 'view')
                continue;

            if (typeof (route.query[key]) == 'string')
                filters.push(getParsedFilter(key, route.query[key]));
            else {
                route.query[key].forEach((v) => {
                    filters.push(getParsedFilter(key, v));
                });
            }
        }
    }
    if (filters.length)
        return filters;
    // show config filters if no query params
    return config_settings.data.filters;
});

const handleFilterChange = async () => {
    let q = {};
    listConfig.value.filters.map((f) => {
        let fieldname = f[0];
        let fieldtype = listConfig.value.fields.find((field) => field.value == fieldname).type;
        let val = (fieldtype == "Check") ? f[2] == "true" : f[2];
        let value = JSON.stringify([f[1], val]);
        if (q[fieldname])
            q[fieldname].push(value);
        else
            q[fieldname] = [value];
    });
    router.replace({ query: q });
    await list.fetch();
};
</script>