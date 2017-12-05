frappe.pages['chirp'].on_page_load = (container) => {
    const page = new frappe.ui.Page({
        title: __('Chat'), parent: container
    })
    const $container = $(container).find('.layout-main')
    $container.html("")

    const chat = new frappe.Chat('.layout-main', {
        layout: frappe.Chat.Layout.PAGE
    })
}