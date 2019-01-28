<template>
    <div class="modules-page-container">
        <div v-if="!route_str" >
             <div v-for="category in module_categories"
                :key="category">

                <div v-if="modules.filter(m => m.category === category).length" class="module-category h6 uppercase">
                    {{ category }}
                </div>

                <div class="modules-container">
                    <div v-for="module in modules.filter(m => m.category === category )"
                        :key="module.name"
                        class="border module-box flush-top"
                        @click="update_state(module.module_name, module.label, module.type, module.link)"
                    >
                        <div class="icon-box">
                            <span><i class="icon text-extra-muted" :class="module.icon"></i></span>
                        </div>
                        <div class="module-box-content">
                            <h4 class="h4"> 
                                {{ module.label }} 
                                <span v-if="module.count" class="open-notification global">{{ module.count }}</span>
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
            module_categories: ["Modules", "Domains", "Places", "Administration"],
            modules: []
        };
    },
    created() {
        this.get_modules();
    },
    mounted() {
        frappe.module_links = {};
        frappe.route.on('change', () => {
            if(frappe.get_route()[0] === 'modules' || !frappe.get_route()[0]) {
                let module = frappe.get_route()[1];
                this.update_module(module);
            }
        });
    },
    methods: {
        update_state(name, label, type, link) {
            if(type === "module") {
                this.module_label = label;
                frappe.set_route(['modules', name]);
            } else if(type === "link") {
                frappe.set_route(link);
            }
        },

        update_module(module) {
            this.route_str = module;
            let title = this.module_label ? this.module_label : module;
            title = module!=='home' ? title : 'Modules';
            frappe.modules.home.page.set_title(title);
        },

        get_modules() {
			let res = frappe.call({
				method: 'frappe.desk.doctype.desktop_icon.desktop_icon.get_modules_from_all_apps',
			});

			res.then(r => {
				if (r.message) {
                    let modules_list = r.message;

                    modules_list = modules_list
                        .filter(d => (d.type==='module' || d.category==='Places') && !d.blocked);

                    modules_list.forEach(module => {
                        module.count = this.get_module_count(module.module_name);
                    });

                    this.modules = modules_list;
                }
            });
        },

        get_module_count(module_name) {
            var module_doctypes = frappe.boot.notification_info.module_doctypes[module_name];
            var sum = 0;

            if(module_doctypes && frappe.boot.notification_info.open_count_doctype) {
                // sum all doctypes for a module
                for (var j=0, k=module_doctypes.length; j < k; j++) {
                    var doctype = module_doctypes[j];
                    let count = (frappe.boot.notification_info.open_count_doctype[doctype] || 0);
                    count = typeof count == "string" ? parseInt(count) : count;
                    sum += count;
                }
            }

            if(frappe.boot.notification_info.open_count_doctype
                && frappe.boot.notification_info.open_count_doctype[module_name]!=null) {
                // notification count explicitly for doctype
                let count = frappe.boot.notification_info.open_count_doctype[module_name] || 0;
                count = typeof count == "string" ? parseInt(count) : count;
                sum += count;
            }

            if(frappe.boot.notification_info.open_count_module
                && frappe.boot.notification_info.open_count_module[module_name]!=null) {
                // notification count explicitly for module
                let count = frappe.boot.notification_info.open_count_module[module_name] || 0;
                count = typeof count == "string" ? parseInt(count) : count;
                sum += count;
            }

            sum = sum > 99 ? "99+" : sum;

            return sum;
        }
    }
}
</script>

<style lang="less" scoped>
.modules-page-container {
    margin: 70px 85px;
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
    padding: 5px 0px;
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

