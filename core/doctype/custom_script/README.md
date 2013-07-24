Client or server script appended to standard DocType code.

For client:

- Code is appended to the js code.
- Best practice is to declare additional methods beginning with prefix `custom_` e.g. `custom_validate` to standard events.

For server:

- Script is appended to module code before DocType is `execute`d. 
- All class methods must be written with a tab