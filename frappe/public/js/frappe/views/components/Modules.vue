<template>
    <div class="modules-page-container">
        <div v-if="!route_str" >
             <div v-for="category in module_categories"
                :key="category">

                <div v-if="category.length" class="module-category h6 uppercase">
                    {{ category }}
                </div>

                <div class="modules-container">
                    <div v-for="module in modules_by_categories[category]"
                        :key="module.name"
                        class="border module-box flush-top"
                        @click="update_state(module.module_name, module.label)"
                    >
                        <div class="icon-box">
                            <span><i class="icon text-extra-muted" :class="module.icon"></i></span>
                        </div>
                        <div class="module-box-content">
                            <h4 class="h4"> 
                                {{ module.label }} 
                                <span class="indicator orange"></span>
                            </h4>
                            <p class="small text-muted"> {{ module.description }} </p>
                        </div>
                    </div>
                </div>

            </div>
        </div>

        <keep-alive v-else-if="modules.map(m => m.module_name).includes(route_str)">
            <module-detail :module_name="route_str"></module-detail>
        </keep-alive>
    </div>
</template>

<script>
import ModuleDetail from './ModuleDetail.vue';

export default {
    components: {
        ModuleDetail
    },
    data() {
        return {
            route_str: frappe.get_route()[1],
            module_label: '',
            module_categories: ["", "Domains", "Places", "Administration"],
            modules_by_categories: {},
            modules: frappe.get_desktop_icons(true)
                .filter(d => (d.type==='module' || d.category==='Places') && !d.blocked),
        };
    },
    created() {
        this.module_categories.map(category => {
            this.modules_by_categories[category] = this.modules.filter(m => m.category === category );
        });
        this.modules_by_categories[""] = this.modules.filter(m => !m.category);
    },
    mounted() {
        frappe.module_links = {};
        frappe.route.on('change', () => {
            let module = frappe.get_route()[1];
            this.update_module(module);
        });
    },
    methods: {
        update_state(name, label) {
            this.module_label = label;
            frappe.set_route(['modules', name]);
        },
        update_module(module) {
            this.route_str = module;
            let title = this.module_label ? this.module_label : module;
            title = module!=='home' ? title : 'Modules';
            frappe.modules.home.page.set_title(title);
        }
    }
}
</script>

<style lang="less" scoped>
.modules-page-container {
    padding: 15px 0px;
    padding-bottom: 30px;
}

.module-category {    
    margin-top: 30px;
    margin-bottom: 15px;
    border-bottom: 1px solid #d0d8dd;
}

.modules-container {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    column-gap: 15px;
    row-gap: 15px;
}

.module-box {
    border-radius: 4px;
    cursor: pointer;
}

.module-box:hover {
    background-color: #fafbfc;
}

.module-box-content {
    padding-right: 15px;
    flex: 1;

    h4 {
        margin-bottom: 5px
    }

    p {
        margin-top: 5px;
        font-size: 80%;
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

</style>

