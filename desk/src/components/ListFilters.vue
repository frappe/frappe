<template>
    <NestedPopover>
        <template #target>
            <Button :label="'Filter'">
                <template #prefix>
                    <FeatherIcon name="filter" class="h-3.5" />
                </template>
                <template v-if="filters?.length" #suffix>
                    <div
                        class="flex h-5 w-5 items-center justify-center rounded bg-gray-900 pt-[1px] text-2xs font-medium text-white">
                        {{ filters?.length }}
                    </div>
                </template>
            </Button>
        </template>
        <template #body="{ close }">
            <div class="my-2 rounded-lg border border-gray-100 bg-white shadow-xl">
                <div class="w-[30rem] p-2">
                    <div v-if="filters?.length"
                        v-for="({ fieldname, fieldtype, operator, value, options }, i) in filters" id="filter-list"
                        class="mb-3 flex items-center justify-between gap-2">
                        <div class="flex items-center gap-2">
                            <div class="w-[9rem]">
                                <Autocomplete :body-classes="'w-[15rem]'" :model-value="fieldname"
                                    :options="allFilterableFields"
                                    @update:model-value="(option) => updateField(option, i)" />
                            </div>
                            <div class="w-[7rem]">
                                <FormControl type="select" :model-value="operator" :options="getOperators(i)"
                                    @update:model-value="(option) => updateOperator(option, i)" />
                            </div>
                            <div class="w-[10rem]">
                                <!-- Added :key to correctly re-render dynamic child component -->
                                <ListFilterValue :fieldtype="fieldtype" :operator="operator" :value="value" :options="options"
                                    @update="(val) => updateValue(val, i)" :key="fieldname"></ListFilterValue>
                            </div>
                        </div>
                        <Button :class="'h-3.5'" variant="ghost" icon="x" @click="removeFilter(i)" />
                    </div>
                    <div v-else class="px-3 my-3 text-sm text-gray-600">
                        {{ 'No filters added.' }}
                    </div>
                    <div class="flex items-center justify-between gap-2">
                        <Autocomplete :body-classes="'w-[29rem]'" :options="allFilterableFields"
                            @update:model-value="(option) => addFilter(option)">
                            <template #target="{ togglePopover }">
                                <Button class="!text-gray-600" variant="ghost" @click="togglePopover()" :label="'Add'">
                                    <template #prefix>
                                        <FeatherIcon name="plus" class="h-3.5" />
                                    </template>
                                </Button>
                            </template>
                        </Autocomplete>
                        <Button v-if="filters?.length" class="!text-gray-600 h-3.5" variant="ghost" :label="'Clear'"
                            @click="clearFilters">
                            <template #prefix>
                                <FeatherIcon name="trash" class="h-3.5" />
                            </template>
                        </Button>
                    </div>
                </div>
            </div>
        </template>
    </NestedPopover>
</template>

<script setup>
import ListFilterValue from '@/components/ListFilterValue.vue';
import NestedPopover from '@/components/Controls/NestedPopover.vue';

import { Button, FeatherIcon, Autocomplete, FormControl } from 'frappe-ui';
import { getCurrentInstance } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const props = defineProps({
    allFilterableFields: {
        type: Array,
        default: [],
    },
});

const filters = defineModel();

// Set up operator options for different fieldtypes

const typeCheck = ['Check'];
const typeLink = ['Link', 'Dynamic Link'];
const typeNumber = ['Float', 'Int', 'Currency', 'Percent'];
const typeSelect = ['Select'];
const typeString = ['Data', 'Long Text', 'Small Text', 'Text Editor', 'Text'];
const typeDate = ['Date', 'Datetime'];

const getOperators = (index) => {
    let f = filters.value[index];
    let fieldname = f.fieldname;
    let fieldtype = f.fieldtype;
    let options = [];
    if (typeString.includes(fieldtype)) {
        options.push(
            ...[
                { label: 'Equals', value: '=' },
                { label: 'Not Equals', value: '!=' },
                { label: 'Like', value: 'like' },
                { label: 'Not Like', value: 'not like' },
                { label: 'In', value: 'in' },
                { label: 'Not In', value: 'not in' },
                { label: 'Is', value: 'is' },
            ]
        )
    }
    if (fieldname === '_assign') {
        // TODO: make equals and not equals work
        options = [
            { label: 'Like', value: 'like' },
            { label: 'Not Like', value: 'not like' },
            { label: 'Is', value: 'is' },
        ]
    }
    if (typeNumber.includes(fieldtype)) {
        options.push(
            ...[
                { label: 'Equals', value: '=' },
                { label: 'Not Equals', value: '!=' },
                { label: 'Like', value: 'like' },
                { label: 'Not Like', value: 'not like' },
                { label: 'In', value: 'in' },
                { label: 'Not In', value: 'not in' },
                { label: 'Is', value: 'is' },
                { label: '<', value: '<' },
                { label: '>', value: '>' },
                { label: '<=', value: '<=' },
                { label: '>=', value: '>=' },
            ]
        )
    }
    if (typeSelect.includes(fieldtype)) {
        options.push(
            ...[
                { label: 'Equals', value: '=' },
                { label: 'Not Equals', value: '!=' },
                { label: 'In', value: 'in' },
                { label: 'Not In', value: 'not in' },
                { label: 'Is', value: 'is' },
            ]
        )
    }
    if (typeLink.includes(fieldtype)) {
        options.push(
            ...[
                { label: 'Equals', value: '=' },
                { label: 'Not Equals', value: '!=' },
                { label: 'Like', value: 'like' },
                { label: 'Not Like', value: 'not like' },
                { label: 'In', value: 'in' },
                { label: 'Not In', value: 'not in' },
                { label: 'Is', value: 'is' },
            ]
        )
    }
    if (typeCheck.includes(fieldtype)) {
        options.push(...[{ label: 'Equals', value: '=' }])
    }
    if (['Duration'].includes(fieldtype)) {
        options.push(
            ...[
                { label: 'Like', value: 'like' },
                { label: 'Not Like', value: 'not like' },
                { label: 'In', value: 'in' },
                { label: 'Not In', value: 'not in' },
                { label: 'Is', value: 'is' },
            ]
        )
    }
    if (typeDate.includes(fieldtype)) {
        options.push(
            ...[
                { label: 'Is', value: 'is' },
                { label: '>', value: '>' },
                { label: '<', value: '<' },
                { label: '>=', value: '>=' },
                { label: '<=', value: '<=' },
                { label: 'Between', value: 'between' },
                { label: 'Timespan', value: 'timespan' },
            ]
        )
    }
    return options;
}

// Filter Operations

const addFilter = (option) => {
    filters.value.push({
        fieldname: option.value,
        fieldtype: getFieldType(option.value),
        options: getSelectOptions(option.value),
        operator: '',
        value: '',
    });
};

const removeFilter = (index) => {
    filters.value.splice(index, 1);
    updateFiltersInQuery();
};

const clearFilters = () => {
    filters.value.splice(0, filters.value.length);
    updateFiltersInQuery();
};

// Update filter options on change of filter field

const getFieldType = (fieldname) => {
    return props.allFilterableFields.find((f) => f.value === fieldname).type || '';
};

const getSelectOptions = (fieldname) => {
    return props.allFilterableFields.find((f) => f.value === fieldname).options?.split("\n") || [];
};

const updateField = (option, index) => {
    filters.value[index] = { fieldname: option.value, fieldtype: getFieldType(option.value), options: getSelectOptions(option.value), operator: '', value: '' };
};

const updateOperator = (option, index) => {
    filters.value[index] = { ...filters.value[index], operator: option, value: '' };
};

const updateValue = (value, index) => {
    let filter = filters.value[index];
    let val = value.target ? value.target.value : value;
    filter.value = val;
    updateFiltersInQuery();
};

// Update filters in query params

const route = useRoute();
const router = useRouter();
const instance = getCurrentInstance();

const updateFiltersInQuery = async () => {
    let q = { view: route.query.view };
    filters.value.map((f) => {
        let fieldname = f.fieldname;
        let value = JSON.stringify([f.operator, getFilterValue(f)]);
        if (q[fieldname])
            q[fieldname].push(value);
        else
            q[fieldname] = [value];
    });
    await router.replace({ query: q });
    instance.parent.emit('update');
};

const getFilterValue = (filter) => {
    if (filter.fieldtype == 'Check') {
        return filter.value == 'true';
    }
    return filter.value;
};
</script>