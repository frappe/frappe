frappe.pages.chat.on_page_load = function (container)
{
    const page = new frappe.ui.Page({
        title: __('Chat'), parent: container
    })
    const $container = $(container).find('.layout-main')
    $container.html("")

    const chat = new frappe.Chat($container,
    {
        layout: frappe.Chat.Layout.PAGE
    });
    chat.render();
};