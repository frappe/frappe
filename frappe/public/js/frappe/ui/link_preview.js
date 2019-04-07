frappe.provide('frappe.pages');

frappe.ui.LinkPreview = class {

    constructor() {
        this.$links = [];
        this.popover_timeout = null
        this.get_links();
    }

    get_links() {
        $(document.body).on('mouseover', 'a[href*="/"]', (e) => {
            this.link_hovered = true;
            let link = $(e.currentTarget).attr('href');
            let link_arr = link.split('/');
            const link_element = $(e.currentTarget);
            let popover = link_element.data("bs.popover");
            this.setup_popover_control(popover, link_arr, link_element);
        });
    }

    setup_popover_control(popover, link_arr, $link) {
        if(!popover) {
            if(link_arr.length > 2) {
                let name = decodeURI(link_arr[link_arr.length - 1]);
                let doctype = decodeURI(link_arr[link_arr.length -2]);
                let preview_fields = this.get_preview_fields(doctype);
                if(preview_fields.length) {
                    this.data_timeout = setTimeout(() => {
                        this.get_preview_fields_value(doctype, name, preview_fields).then((preview_data)=> {
                            if(preview_data) {
                                if (this.popover_timeout) {
                                    clearTimeout(this.popover_timeout)
                                }
                                this.popover_timeout = setTimeout(() => {
                                    this.init_preview_popover($link, preview_data, doctype);
                                }, 1000);
                            }
                        });
                    }, 1000);
                    
                }
            }
        } else {
            this.popover_timeout = setTimeout(() => {
                popover.show();
            }, 1000);
        }

        $(document.body).on('mouseout', 'a[href*="/"]', () => {
            this.link_hovered = false;
            if(this.data_timeout) {
                clearTimeout(this.data_timeout)
            }
            if (this.popover_timeout) {
                clearTimeout(this.popover_timeout)
            }
        })
        $(document.body).on('mousemove', () => {
            if (!this.link_hovered) {
                this.$links.forEach($link => $link.popover('hide'));
            }
        })
    }

    get_preview_fields(dt) {
        let fields = []
        frappe.model.with_doctype(dt, () => { 
            frappe.get_meta(dt).fields.filter((field) => {
                if(field.in_preview) fields.push(field.fieldname);
            })
        });
        return fields;
    }

    get_preview_fields_value(dt, field_name, field_list) {
        return frappe.xcall('frappe.client.get_preview_data', {
            'doctype': dt,
            'docname': field_name,
            'fields': field_list
        });
    }

    init_preview_popover($link, preview_data, dt) {
        console.log('create popover')
        let content_html = '';
        console.log('preview_data', preview_data);

        Object.keys(preview_data).forEach(key => {
            content_html += `
                <p class="link-preview-field text-regular">
                    <b> ${frappe.meta.get_label(dt, key)} </b>:  ${preview_data[key]} 
                </p>
            `;
        })

        $link.popover({
            container: 'body',
            html: true,
            content: content_html,
            trigger: 'manual',
            animation: false
            // delay: {'show':show_delay,'hide':hide_delay}
        });
        this.$links.push($link);
        $link.popover('show');

        // $link.data('bs.popover').options.content = content_html;
        // $link.popover('show');
        // setTimeout(() => {
        //     $link.popover('show')
        // }, 1000);

    
        // $link.mouseleave(() => {
        //     $link.popover('hide')
        // });

    }



}