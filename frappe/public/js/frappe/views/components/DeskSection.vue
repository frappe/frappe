<template>
    <div>
        <div class="section-header level text-muted">
            <div class="module-category h6 uppercase">
            {{ category }}
            </div>

            <div>
                <a class="small text-muted" @click="show_customize_dialog">{{ __("Customize") }}</a>
            </div>
        </div>

        <div class="modules-container">
            <a v-for="module in modules"
                :key="module.name"
                :href="module.type === 'module' ? '#modules/' + module.module_name : module.link"
                class="border module-box"
            >
                <div class="flush-top">
                    <div class="module-box-content">
                        <h4 class="h4">
                            <span class="indicator" :class="module.count ? 'red' : (module.onboard_present ? 'orange' : 'grey')"></span>
                            {{ module.label }}
                        </h4>
                        <p
                            v-if="module.shortcuts"
                            class="small text-muted">
                                <button
                                    v-for="shortcut in module.shortcuts"
                                    :key="shortcut"
                                    class="btn btn-default btn-xs shortcut-tag" title="toggle Tag"> {{ shortcut }}
                                </button>
                        </p>
                        <p v-else> {{ module.description }} </p>
                    </div>
                </div>
            </a>
        </div>
    </div>
</template>

<script>
export default {
    props: ['category', 'initial_modules'],
    data() {
        return {
            modules: this.initial_modules
        }
    },
    methods: {
        show_customize_dialog() {
            let fields = [];

            this.modules.forEach(module => {
                fields.push({
                    label: __(module.module_name),
                    fieldname: module.module_name,
                    fieldtype: "Check",
                    default: 1
                });

                if(module.shortcuts) {
                    fields.push({
                        label: __(""),
                        fieldname: module.module_name + "_shortcuts",
                        fieldtype: "MultiSelect",
                        options: module.shortcuts,
                        default: module.shortcuts,
                        depends_on: module.module_name
                    });
                }
            });

            let dialog = new frappe.ui.Dialog({
                title: __("Customize " + this.category),
                fields: fields
            });

            dialog.show();
        }
    }
}
</script>

<style lang="less" scoped>
.shortcut-header {
	margin-top: 30px;
	margin-bottom: 15px;
	border-bottom: 1px solid #d0d8dd;
}

.modules-container {
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
	grid-auto-rows: minmax(72px, 1fr);
	column-gap: 15px;
	row-gap: 15px;
}

.module-box {
	border-radius: 4px;
	cursor: pointer;
	padding: 5px 15px;
    padding-top: 3px;
	display: block;
}

.module-box:hover {
	background-color: #fafbfc;
	text-decoration: none;
}

.module-box-content {
    width: 100%;

	h4 {
		margin-bottom: 5px
	}

	p {
		margin-top: 5px;
        font-size: 80%;
        display: flex;
        overflow: hidden;
	}
}

.icon-box {
	padding: 15px;
	width: 54px;
	display: flex;
	justify-content: center;
}

.icon {
	font-size: 24px;
}

.open-notification {
	top: -2px;
}

.shortcut-tag {
    margin-right: 5px;
}
</style>

