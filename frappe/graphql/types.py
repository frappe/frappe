import graphene

from frappe.graphql.utils import make_object_field
from frappe.graphql.utils import make_object_resolver

from graphene.types.objecttype import ObjectType, ObjectTypeOptions


frappe_graphene = {
    'Currency': graphene.Decimal,
    'Int': graphene.Int,
    'Long Int': graphene.Int,
    'Float': graphene.Float,
    'Percent': graphene.Float,
    'Check': graphene.Boolean,
    'Small Text': graphene.String,
    'Long Text': graphene.String,
    'Code': graphene.String,
    'Text Editor': graphene.String,
    'Markdown Editor': graphene.String,
    'HTML Editor': graphene.String,
    'Date': graphene.Date,
    'Datetime': graphene.DateTime,
    'Time': graphene.Time,
    'Text': graphene.String,
    'Data': graphene.String,
    'Link': graphene.Field,
    'Dynamic Link': graphene.String,
    'Select': graphene.String,
    'Rating': graphene.Float,
    'Read Only': graphene.String,
    'Signature': graphene.String,
    'Color': graphene.String,
    'Barcode': graphene.String,
    'Geolocation': graphene.String,
}
frappe_not_include = [
    'Password',
    'Attach',
    'Attach Image',
]


class FrappeObjectType(graphene.ObjectType):
    @classmethod
    def __init_subclass_with_meta__(
        cls,
        doctype=None,
        interfaces=(),
        possible_types=(),
        default_resolver=None,
        _meta=None,
        **options
    ):
        fields = make_object_field(doctype)
        make_object_resolver(cls, doctype)

        # create _meta object
        if not _meta:
            _meta = ObjectTypeOptions(cls)

        if _meta.fields:
            _meta.fields.update(fields)
        else:
            _meta.fields = fields

        if not _meta.interfaces:
            _meta.interfaces = interfaces
        _meta.possible_types = possible_types
        _meta.default_resolver = default_resolver

        super(ObjectType, cls).__init_subclass_with_meta__(
            _meta=_meta, **options
        )
