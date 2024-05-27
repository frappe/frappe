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
                    <div v-if="filters?.length" v-for="(filter, i) in filters" id="filter-list"
                        class="mb-3 flex items-center justify-between gap-2">
                        <div class="flex items-center gap-2">
                            <div id="fieldname" class="w-[9rem]">
                                <Autocomplete :body-classes="'w-[15rem]'" :modelValue="filter[0]"
                                    :options="allFilterableFields"
                                    @update:model-value="(option) => updateField(option, filter)" />
                            </div>
                            <div id="operator" class="w-[7rem]">
                                <FormControl type="select" v-model="filter[1]" :options="getOperators(filter[0])"
                                    @change="filter[2] = ''" />
                            </div>
                            <div id="value" class="w-[10rem]">
                                <component :is="getValSelect(filter, close)" v-model="filter[2]"
                                    @change="(v) => updateValue(v, filter)" />
                            </div>
                        </div>
                        <Button :class="'h-3.5'" variant="ghost" icon="x" @click="removeFilter(i)"/>
                    </div>
                    <div v-else class="mb-3 flex h-7 items-center px-3 text-sm text-gray-600">
                        {{ 'Empty - Choose a field to filter by' }}
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
                        <Button v-if="filters?.length" class="!text-gray-600 h-3.5" variant="ghost" icon="trash"
                            @click="clearFilters" />
                    </div>
                </div>
            </div>
        </template>
    </NestedPopover>
</template>

<script setup>
import DatePicker from '@/components/Controls/DatePicker.vue';
import DatetimePicker from '@/components/Controls/DatetimePicker.vue';
import DateRangePicker from '@/components/Controls/DateRangePicker.vue';
import Link from '@/components/Controls/Link.vue';

import NestedPopover from '@/components/Controls/NestedPopover.vue';
import { Button, FeatherIcon, Autocomplete, FormControl } from 'frappe-ui';
import { h, getCurrentInstance } from 'vue';

const props = defineProps({
    allFilterableFields: {
        type: Array,
        default: [],
    },
});
const filters = defineModel();

const getFieldType = (fieldname) => {
    return props.allFilterableFields.find((f) => f.value === fieldname).type || '';
};

function getOperators(fieldname) {
    let fieldtype = getFieldType(fieldname);
    let options = []
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
    return options
}

const typeCheck = ['Check']
const typeLink = ['Link', 'Dynamic Link']
const typeNumber = ['Float', 'Int', 'Currency', 'Percent']
const typeSelect = ['Select']
const typeString = ['Data', 'Long Text', 'Small Text', 'Text Editor', 'Text']
const typeDate = ['Date', 'Datetime']
const timespanOptionsList = [
    {
        label: 'Last Week',
        value: 'last week',
    },
    {
        label: 'Last Month',
        value: 'last month',
    },
    {
        label: 'Last Quarter',
        value: 'last quarter',
    },
    {
        label: 'Last 6 Months',
        value: 'last 6 months',
    },
    {
        label: 'Last Year',
        value: 'last year',
    },
    {
        label: 'Yesterday',
        value: 'yesterday',
    },
    {
        label: 'Today',
        value: 'today',
    },
    {
        label: 'Tomorrow',
        value: 'tomorrow',
    },
    {
        label: 'This Week',
        value: 'this week',
    },
    {
        label: 'This Month',
        value: 'this month',
    },
    {
        label: 'This Quarter',
        value: 'this quarter',
    },
    {
        label: 'This Year',
        value: 'this year',
    },
    {
        label: 'Next Week',
        value: 'next week',
    },
    {
        label: 'Next Month',
        value: 'next month',
    },
    {
        label: 'Next Quarter',
        value: 'next quarter',
    },
    {
        label: 'Next 6 Months',
        value: 'next 6 months',
    },
    {
        label: 'Next Year',
        value: 'next year',
    },
]

function getValSelect(f, close) {
    const field = f[0];
    const operator = f[1];
    const fieldtype = getFieldType(field);
    const options = props.allFilterableFields.find((f) => f.value == field).options;
    if (operator == 'is') {
        return h(FormControl, {
            type: 'select',
            options: [
                {
                    label: 'Set',
                    value: 'set',
                },
                {
                    label: 'Not Set',
                    value: 'not set',
                },
            ],
        })
    } else if (operator == 'timespan') {
        return h(FormControl, {
            type: 'select',
            options: timespanOptionsList,
        })
    } else if (['like', 'not like', 'in', 'not in'].includes(operator)) {
        return h(FormControl, { type: 'text' })
    } else if (typeSelect.includes(fieldtype) || typeCheck.includes(fieldtype)) {
        const _options =
            fieldtype == 'Check' ? ['Yes', 'No'] : getSelectOptions(options)
        let check_values = { 'Yes': true, 'No': false };
        return h(FormControl, {
            type: 'select',
            options: _options.map((o) => ({
                label: o,
                value: check_values[o] || o,
            })),
        })
    } else if (typeLink.includes(fieldtype)) {
        if (fieldtype == 'Dynamic Link') {
            return h(FormControl, { type: 'text' })
        }
        return h(Link, { class: 'form-control', doctype: options, value: f[2] })
    } else if (typeNumber.includes(fieldtype)) {
        return h(FormControl, { type: 'number' })
    } else if (typeDate.includes(fieldtype) && operator == 'between') {
        return h(DateRangePicker, { value: f[2]})
    } else if (typeDate.includes(fieldtype)) {
        return h(fieldtype == 'Date' ? DatePicker : DatetimePicker, {
            value: f[2],
        })
    } else {
        return h(FormControl, { type: 'text' })
    }
}

const updateField = (option, filter) => {
    filter[0] = option.value;
    filter[1] = '';
    filter[2] = '';
};
const instance = getCurrentInstance();

function updateValue(value, filter) {
    value = value.target ? value.target.value : value;
    if (filter[1] === 'between') {
        filter[2] = [value.split(',')[0], value.split(',')[1]]
    } else {
        filter[2] = value
    }
    instance.parent.emit('updateFilter');
};

const addFilter = (option) => {
    filters.value.push([option.value, '', '']);
};

const removeFilter = (index) => {
    filters.value.splice(index, 1);
    instance.parent.emit('updateFilter');
};

const clearFilters = () => {
    filters.value = [];
    instance.parent.emit('updateFilter');
};
</script>