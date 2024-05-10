DocType is the basic building block of an application and encompasses all the three elements i.e. model, view and controller. It represents a:

- Table in the database
- Form in the application
- Controller (class) to execute business logic

#### Single Type

DocTypes can be of "Single" type where they do not represent a table, and only one instance is maintained. This can be used where the DocType is required only for its view features or to store some configurations in one place.

#### Child Tables

DocTypes can be child tables of other DocTypes. In such cases, they must defined `parent`, `parenttype` and `parentfield` properties to uniquely identify its placement.

In the parent DocType, the position of a child in the field sequence is defined by the `Table` field type.