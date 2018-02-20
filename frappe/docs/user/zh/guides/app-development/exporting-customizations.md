# Exporting Customizations to your App

A common use case is to extend a DocType via Custom Fields and Property Setters for a particular app. To save these settings to an app, go to **Customize Form**

You will see a button for **Export Customizations**

<img class="screenshot" src="/docs/assets/img/app-development/export-custom-1.png">

Here you can select the module and whether you want these particular customizations to be synced after every update.

The customizations will be exported to a new folder `custom` in the module folder of your app. The customizations will be saved by the name of the DocType

<img class="screenshot" src="/docs/assets/img/app-development/export-custom-2.png">

When you do `bench update` or `bench migrate` these customizations will be synced to the app.