# Tutorial sobre Frappé

En esta guía, vamos a mostrarte como crear una aplicación desde cero usando **Frappé**. Usando el ejemplo de un Sistema de Gestión de Librería. Vamos a cubrir:

1. Instalación
1. Creando una nueva App
1. Creando Modelos
1. Creando Usuarios y Registros
1. Creando Controladores
1. Creando Vistas Web
1. Configurando Hooks y Tareas

## Para Quién es este tutorial?

Esta guía esta orientada para desarrolladores de software que estan familiarizados con el proceso de como son creadas y servidas las aplicaciones web. El Framework Frappé está escrito en Python y usa MariaDB como base de datos y para la creación de las vistas web usa HTML/CSS/Javascript. Por lo que sería excelente si estas familiarizado con estas tecnologías.
Por lo menos, si nunca haz usado Python antes, deberías tomar un tutorial rápido antes de iniciar con este tutorial.

Frappé usa el sistema de gestión de versiones en GitHub. También, es importante estar familiarizado con los conceptos básicos de git y tener una cuenta en GitHub para manejar sus aplicaciones.

## Ejemplo

Para esta guía, vamos a crear una aplicación simple llamada **Library Management**. En esta aplicación vamos a tener los siguientes modelos (Permanecerán en inglés para que coincidan con las imagenes):

1. Article (Libro o cualquier otro artículo que pueda ser prestado)
1. Library Member
1. Library Transaction (Entrega o Retorno de un artículo)
1. Library Membership (Un período en el que un miembro esta permitido hacer una trasacción)
1. Library Management Setting (Configuraciones generales, como el tiempo que dura el prestamo de un artículo)

La interfaz de usuario (UI) para la aplicación va a ser el **Frappé Desk**, un entorno para UI basado en el navegador y viene integrado en Frappé donde los formularios son generados automáticamente desde los modelos y los roles y permisos son aplicados.

También, vamos a crear vistas webs para la librería donde los usuarios pueden buscar los artículos desde una página web.

{index}
