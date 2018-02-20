# Frappé Tutorial

In this guide we will show you how to create an application from scratch using **Frappé**. Using the example of a Library Management System, we will cover:

1. Installation
1. Making a New App
1. Making Models
1. Creating Users and Records
1. Creating Controllers
1. Creating Web Views
1. Setting Hooks and Tasks

## Who is This For?

This guide is intended for software developers who are familiar with how the web applications are built and served. Frappé Framework is built on Python and uses MariaDB database and for creating web views, HTML/CSS/Javascript is used. So it would be great if you are familiar with all these technologies. At minimum if you have never used Python before, you should take a quick tutorial before your use this Guide.

Frappé uses the git version control system on GitHub. It is also important that you are familiar with basic git and have an account on GitHub to manage your applications.

## Example

For this guide book, we will build a simple **Library Management** application. In this application we will have models:

1. Article (Book or any other item that can be loaned)
1. Library Member
1. Library Transaction (Issue or Return of an article)
1. Library Membership (A period in which a member is allowed to transact)
1. Library Management Setting (Global settings like period of loan)

The user interface (UI) for the librarian will be the **Frappé Desk**, a built-in browser based UI environment where forms are automatically generated from the models and roles and permissions are also applied.

We will also create web views for library where users can browse articles from a website.

{index}
