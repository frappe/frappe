frappe.provide('frappe.pages');

frappe.ui.LinkPreview = class {

    constructor() {
        this.$links = [];
        this.popover_timeout = null
        this.get_links();
    }

    get_links() {
        $(document.body).on('mouseover', 'a[href*="/"], input[data-fieldname], .popover', (e) => {
            this.link_hovered = true;
            let element = $(e.currentTarget);
            let name;
            let doctype;
            let is_link = true;
            let link_control;
            if(element.attr('href')) {
                let link = element.attr('href');
                let link_arr = link.split('/');
                if(link_arr.length > 2) {
                    name = decodeURI(link_arr[link_arr.length - 1]);
                    doctype = decodeURI(link_arr[link_arr.length -2]);
                }           
            }
            else {
                is_link = false;
                // let linked_field = element.parents('.link-field').find('.link-btn')
                // if(linked_field.length) {
                // console.log('yes linked field', linked_field)
                link_control = element.parents('.control-input-wrapper').find('.control-value').children('a').attr('href');
                console.log(link_control);
                if(link_control) {
                    let link_arr = link_control.split('/');
                    console.log('arr', link_arr);
                    if(link_arr.length > 2) {
                        name = decodeURI(link_arr[link_arr.length - 1]);
                        doctype = decodeURI(link_arr[link_arr.length -2]);
                    }
                }
                // }
                else {
                    name = element.parent().next().text();
                    doctype = element.attr('data-doctype');
                }
            }
            let popover = element.data("bs.popover");
            if(name && doctype) {
                this.setup_popover_control(e, popover, name, doctype, element, is_link, link_control);
            }
        });
    }


    setup_popover_control(e, popover, name, doctype, $link, is_link, link_control) {
        if(!popover || !is_link) {
                let preview_fields = this.get_preview_fields(doctype);
                if(preview_fields.length) {
                    this.data_timeout = setTimeout(() => {
                        this.get_preview_fields_value(doctype, name, preview_fields).then((preview_data)=> {
                            if(preview_data) {
                                console.log('preview', preview_data);
                                if (this.popover_timeout) {
                                    clearTimeout(this.popover_timeout)
                                }
                                this.popover_timeout = setTimeout(() => {
                                    if(popover) {
                                        let new_content = this.get_content_html(preview_data, doctype, link_control)
                                        popover.options.content = new_content;
                                    }
                                    else {
                                        this.init_preview_popover($link, preview_data, doctype, is_link, link_control);
                                    }
                                    if(!is_link) {
                                        var left = e.pageX;
                                        $link.popover('show');
                                        $('.control-field-popover').css('left', (left+30) + 'px');
                                    }                              
                                    else {
                                        $link.popover('show');
                                    }
                                }, 1000);
                            }
                        });
                    }, 1000);
            }
        } else {
            this.popover_timeout = setTimeout(() => {
                popover.show();
            }, 1000);
        }

        $(document.body).on('mouseout', 'a[href*="/"], input[data-fieldname], .popover', () => {
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

    init_preview_popover($link, preview_data, dt, is_link, link_control) {
        console.log('preview_data', preview_data);
        let content_html = this.get_content_html(preview_data, dt, link_control);
        console.log('content', content_html)
        $link.popover({
            container: 'body',
            html: true,
            content: content_html,
            trigger: 'manual',
            // placement: !is_link?'auto bottom':'auto right',
            animation: false
            // delay: {'show':show_delay,'hide':hide_delay}
        });
        if(!is_link) {
            $link.data('bs.popover').tip().addClass('control-field-popover');
        }
        this.$links.push($link);
        // return content_html;
        // $link.data('bs.popover').options.content = content_html;
        // $link.popover('show');
        // setTimeout(() => {
        //     $link.popover('show')
        // }, 1000);

    
        // $link.mouseleave(() => {
        //     $link.popover('hide')
        // });

    }

    get_content_html(preview_data, dt, link_control) {
        let content_html = '';
        if(preview_data['image']) {
            let image_url = encodeURI(preview_data['image']);
            content_html += `
            <div class="link-preview-field">
                <img src=${image_url} style="max-width:200px; max-height:150px"></img> 
            </div>
        `;
        }
        Object.keys(preview_data).forEach(key => {
            if(key!='image'){
                content_html += `
                    <p class="link-preview-field" style="font-size:0.9em">
                        <b> ${frappe.meta.get_label(dt, key)} </b>:  ${preview_data[key]} 
                    </p>
                `;
            }
        })
        if(link_control) {
            content_html+= `<a href=${link_control}><span>${'View'}</span></a>`
        }
        return content_html;
    }



}