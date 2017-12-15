# DocType Naming and Linking

Then let us create the other DocType and save it too:

1. Library Member (First Name, Last Name, Email Address, Phone, Address)

<img class="screenshot" alt="Doctype Saved" src="/docs/assets/img/naming_doctype.png">


#### Naming of DocTypes

DocTypes can be named in different ways:

1. Based on a field
1. Based on a series
1. By controller (code)
1. Prompt

This can be set by entering the **Autoname** field. For controller, leave blank.

> **Search Fields**: A DocType may be named on a series but it still needs to be searched by name. In our case, the Article will be searched by the title or the author name. So this can be entered in search field.

<img class="screenshot" alt="Autonaming and Search Field" src="/docs/assets/img/autoname_and_search_field.png">

#### Link and Select Fields

Foreign keys are specified in Frappé as **Link** type fields. The target DocType must be mentioned in the Options text area.

In our example, in the Library Transaction DocType, we have to link both the Library Member and the Article.

**Note:** Remeber that Link fields are not automatically set as Foreign Keys in the MariaDB database, because that will implicitly index the column. This may not be optimum hence the Foreign Key validation is done by the Framework.

<img class="screenshot" alt="Link Field" src="/docs/assets/img/link_field.png">

For select fields, as we mentioned earlier, add the various options in the **Options** input box, each option on a new row.

<img class="screenshot" alt="Select Field" src="/docs/assets/img/select_field.png">

Similary complete making the other models.

#### Linked Values

A standard pattern is when you select an ID, say **Library Member** in **Library Membership**, then the Member's first and last names should be copied into relevant fields in the Library Membership Transaction.

To do this, we can use Read Only fields and in options, we can set the the name of the link and the fieldname of the property we want to fetch. For this example in **Member First Name** we can set `library_member.first_name`

<img class="screenshot" alt="Fetch values" src="/docs/assets/img/fetch.png">

### Complete the Models

In the same way, you can complete all the models so that the final fields look like this:

#### Article

<img class="screenshot" alt="Article" src="/docs/assets/img/doctype_article.png">

#### Library Member

<img class="screenshot" alt="Library Member" src="/docs/assets/img/doctype_lib_member.png">

#### Library Membership

<img class="screenshot" alt="Library Membership" src="/docs/assets/img/doctype_lib_membership.png">

#### Library Transaction

<img class="screenshot" alt="Library Transaction" src="/docs/assets/img/doctype_lib_trans.png">

> Make sure to give permissions to **Librarian** on each DocType

{next}
