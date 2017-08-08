# O que é uma aplicação

Uma Aplicação em Frappé é apenas uma aplicação padrão em Python. Você pode estruturar uma aplicação Frappé da mesma forma que estrutura uma aplicação padrão do Python. Para fazer o deploy, Frappé usa o padrão Setuptools do Python, assim você pode facilmente portar e instalar o aplicativo em qualquer máquina.

Frappé Framework fornece uma interface WSGI e para o desenvolvimento você pode usar o servidor embutido Werkzeug. Para a implementação em produção, recomendamos o uso do nginx e gunicorn.

Frappé também tem uma arquitetura multi-tenant, a partir da base. Isso significa que você pode executar vários "sites" em sua configuração, cada um poderia estar servindo um conjunto diferente de aplicativos e usuários. O banco de dados de  cada site é separado.

{next}
