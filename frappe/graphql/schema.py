import frappe
import graphene

from frappe.graphql.types import FrappeObjectType


class Blogger(FrappeObjectType):
    class Meta:
        doctype = 'Blogger'


class BlogPost(graphene.ObjectType):
    name = graphene.String(required=True)
    blog_category = graphene.String()
    route = graphene.String()
    blogger = graphene.Field(Blogger, name=graphene.String())

    def resolve_blogger(root, info, **kwargs):
        name = root.blogger
        doc = frappe.get_doc('Blogger', name).as_dict()
        return Blogger(**doc)


class RootQuery(graphene.ObjectType):
    blog_post = graphene.Field(BlogPost, docname=graphene.String())

    def resolve_blog_post(root, info, **kwargs):
        docname = kwargs.get('docname')
        doc = frappe.get_doc('Blog Post', docname).as_dict()
        return BlogPost(
            name=doc.get('name'),
            blog_category=doc.get('blog_category'),
            blogger=doc.get('blogger'),
        )


schema = graphene.Schema(RootQuery)


def execute():
    query = frappe.form_dict.get('query')
    result = schema.execute(query)

    return result
