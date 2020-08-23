import graphene
import frappe

from frappe.model import no_value_fields
from frappe.model import default_fields

from graphene.types.field import Field
from graphene.types.utils import yank_fields_from_attrs
from collections import OrderedDict


def make_object_field(doctype):
    docfields = frappe.get_all(
        'DocField',
        fields=[
            'fieldname',
            'fieldtype',
        ],
        filters={'parent': doctype}
    )
    customfield = frappe.get_all(
        'Custom Field',
        fields=[
            'fieldname',
            'fieldtype'
        ],
        filters={'dt': doctype}
    )
    docfields.extend(customfield)

    frappe_fields = {}
    for field in docfields:
        frappe_fields[field.get('fieldname')] = graphene.String()

    for field in default_fields:
        frappe_fields[field] = graphene.String()

    fields = OrderedDict()
    fields = yank_fields_from_attrs(
        frappe_fields,
        _as=Field,
    )
    return fields


def make_object_resolver(cls, doctype):
    docfields = frappe.get_all(
        'DocField',
        fields=[
            'fieldname',
            'fieldtype',
        ],
        filters={'parent': doctype}
    )
    customfield = frappe.get_all(
        'Custom Field',
        fields=[
            'fieldname',
            'fieldtype'
        ],
        filters={'dt': doctype}
    )
    docfields.extend(customfield)

    for field in docfields:
        def resolver(self, info):
            return 'abcd'
        resolver_name = 'resolve_{}'.format(field.get('fieldname'))

        setattr(cls, resolver_name, resolver)

    return cls
