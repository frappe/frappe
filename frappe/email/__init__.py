# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from typing import TYPE_CHECKING, Literal, Optional
import frappe

if TYPE_CHECKING:
    from frappe.email.doctype.email_queue.email_queue import EmailQueue


def sendmail_to_system_managers(subject: str, content: str) -> None:
    """Send an email to all System Managers."""
    frappe.sendmail(
        recipients=get_system_managers(),
        subject=subject,
        content=content
    )


@frappe.whitelist()
def get_contact_list(
    txt: str,
    page_length: int = 20,
    extra_filters: str | None = None
) -> list[dict]:
    """Return email ids for a multiselect field."""
    if extra_filters:
        extra_filters = frappe.parse_json(extra_filters)

    filters = [["Contact Email", "email_id", "is", "set"]]
    if extra_filters:
        filters.extend(extra_filters)

    search_fields = ["first_name", "middle_name", "last_name", "company_name"]

    contacts = frappe.get_list(
        "Contact",
        fields=["full_name", "`tabContact Email`.email_id"],
        filters=filters,
        or_filters=[[field, "like", f"%{txt}%"] for field in search_fields]
        + [["Contact Email", "email_id", "like", f"%{txt}%"]],
        limit_page_length=page_length,
    )

    return [
        frappe._dict(value=contact.email_id, label=contact.email_id, description=contact.full_name)
        for contact in contacts
    ]


def get_system_managers() -> list[str]:
    """Fetch emails of all enabled System Managers except Administrator."""
    return frappe.db.sql_list("""
        SELECT parent 
        FROM `tabHas Role`
        WHERE role = 'System Manager'
        AND parent != 'Administrator'
        AND parent IN (SELECT email FROM tabUser WHERE enabled = 1)
    """)


@frappe.whitelist()
def relink(name: str, reference_doctype: str = None, reference_name: str = None) -> None:
    """Link a Communication to a specific document."""
    frappe.db.sql("""
        UPDATE `tabCommunication`
        SET reference_doctype = %s,
            reference_name = %s,
            status = "Linked"
        WHERE communication_type = "Communication"
        AND name = %s
    """, (reference_doctype, reference_name, name))


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_communication_doctype(doctype, txt, searchfield, start, page_len, filters):
    """Fetch doctypes that can be linked to a communication."""
    from frappe.modules import load_doctype_module
    user_perms = frappe.utils.user.UserPermissions(frappe.session.user)
    user_perms.build_permissions()
    can_read = user_perms.can_read

    communication_doctypes = []
    if len(txt) < 2:
        for name in frappe.get_hooks("communication_doctypes"):
            try:
                module = load_doctype_module(name, suffix="_dashboard")
                if hasattr(module, "get_data"):
                    for group in module.get_data()["transactions"]:
                        communication_doctypes += group["items"]
            except ImportError:
                pass
    else:
        communication_doctypes = [
            d[0]
            for d in frappe.db.get_values(
                "DocType",
                {"issingle": 0, "istable": 0, "hide_toolbar": 0}
            )
        ]

    return [
        [dt]
        for dt in communication_doctypes
        if txt.lower().replace("%", "") in dt.lower() and dt in can_read
    ]


def sendmail(
    recipients=None,
    sender: str = "",
    subject: str = "No Subject",
    message: str = "No Message",
    as_markdown: bool = False,
    delayed: bool = True,
    reference_doctype=None,
    reference_name=None,
    unsubscribe_method=None,
    unsubscribe_params=None,
    unsubscribe_message=None,
    add_unsubscribe_link: int = 1,
    attachments=None,
    content=None,
    doctype=None,
    name=None,
    reply_to=None,
    queue_separately: bool = False,
    cc=None,
    bcc=None,
    message_id=None,
    in_reply_to=None,
    send_after=None,
    expose_recipients=None,
    send_priority: int = 1,
    communication=None,
    retry: int = 1,
    now=None,
    read_receipt=None,
    is_notification: bool = False,
    inline_images=None,
    template=None,
    args=None,
    header=None,
    print_letterhead: bool = False,
    with_container: bool = False,
    email_read_tracker_url=None,
    x_priority: Literal[1, 3, 5] = 3,
    email_headers=None,
) -> Optional["EmailQueue"]:
    """
    Send email using the user's default **Email Account** or the global default **Email Account**.
    """

    from frappe.utils.jinja import get_email_from_template

    recipients = recipients or []
    cc = cc or []
    bcc = bcc or []

    text_content = None
    if template:
        message, text_content = get_email_from_template(template, args)

    message = content or message

    if as_markdown:
        from frappe.utils import md_to_html
        message = md_to_html(message)

    if not delayed:
        now = True

    from frappe.email.doctype.email_queue.email_queue import QueueBuilder

    builder = QueueBuilder(
        recipients=recipients,
        sender=sender,
        subject=subject,
        message=message,
        text_content=text_content,
        reference_doctype=doctype or reference_doctype,
        reference_name=name or reference_name,
        add_unsubscribe_link=add_unsubscribe_link,
        unsubscribe_method=unsubscribe_method,
        unsubscribe_params=unsubscribe_params,
        unsubscribe_message=unsubscribe_message,
        attachments=attachments,
        reply_to=reply_to,
        cc=cc,
        bcc=bcc,
        message_id=message_id,
        in_reply_to=in_reply_to,
        send_after=send_after,
        expose_recipients=expose_recipients,
        send_priority=send_priority,
        queue_separately=queue_separately,
        communication=communication,
        read_receipt=read_receipt,
        is_notification=is_notification,
        inline_images=inline_images,
        header=header,
        print_letterhead=print_letterhead,
        with_container=with_container,
        email_read_tracker_url=email_read_tracker_url,
        x_priority=x_priority,
        email_headers=email_headers,
    )

    return builder.process(send_now=now)
