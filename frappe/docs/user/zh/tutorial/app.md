# 什么是应用

Frappé 中的应用只是标准的 Python 应用。 您可以采用与标准 Python 应用相同的方式来构造 Frappé 应用。 对于部署，Frappé 使用标准的 Python Setuptools，因此您可以在任何计算机上轻松地进行应用移植和安装。

Frappé 框架提供了 WSGI 接口，您可以使用内置的 Werkzeug 服务进行开发。 对于生产环境的实施，我们建议使用 Nginx 和 Gunicorn。

Frappé 也拥有多租户架构。 这意味着您可以在安装中运行多个 "站点"，每个都可以为不同的应用和用户提供服务。 每个站点的数据库也是独立的。

{next}