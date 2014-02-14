Defines a permission rule for a DocType. The permission rule is set for a Role and a level and has permission for read, write, create, submit, cancel, amend and report. 

#### Match

If a fieldname is set in `match` property, then the rule will only apply for those records that have a value for that fieldname which is one of the user's default values (user properties).

This is used to restrict users to view records belonging to a company in case of a multi-company system where the `company` field is present in most forms.