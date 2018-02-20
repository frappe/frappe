# Fazendo Usuários e Registros

Agora que já criamos os modelos, podemos começar diretamente criando registros usando a interface Desk do Frappé. Você não precisa criar Views! Views no Frappé são geradas automaticamente com base nas propriedades do DocType.

### 4.1 Criando Usuarios

Para criar registros, vamos primeiro criar um usuário. Para criar um usuário, vá para:

> Setup > Users > User > New

Crie um novo usuário e definá o nome, o primeiro nome e uma nova senha.

Também de as roles de Librarian e Library Member para este usuario

<img class="screenshot" alt="Add User Roles" src="/docs/assets/img/add_user_roles.png">

Agora saia e se autentique usando o novo ID de usuário e senha.

### 4.2 Criando registros

Você vai ver agora um ícone para o módulo de Library Management. Clique nesse ícone e você verá a página do modelo:

<img class="screenshot" alt="Library Management Module" src="/docs/assets/img/lib_management_module.png">

Aqui você pode ver os doctypes que criamos para a aplicação. Vamos começar a criar alguns registros.

Primeiro, vamos criar um novo artigo:

<img class="screenshot" alt="New Article" src="/docs/assets/img/new_article_blank.png">

Aqui você vai ver que o DocType que você tinha criado foi processado como um formulário. As validações e outras regras também serão aplicadas conforme projetado. Vamos preencher um artigo.

<img class="screenshot" alt="New Article" src="/docs/assets/img/new_article.png">

Você também pode adicionar uma imagem.

<img class="screenshot" alt="Attach Image" src="/docs/assets/img/attach_image.gif">

Agora vamos criar um novo membro:

<img class="screenshot" alt="New Library Member" src="/docs/assets/img/new_member.png">

Depois disso, vamos criar um novo registro de membership para o membro.

Aqui se você se lembra, nós tinhamos definido os valores do primeiro e do ultimo nome do membro para ser diretamente obtido a partir dos registros de membros e, logo que você selecionar o ID de membro, os nomes serão atualizados.

<img class="screenshot" alt="New Library Membership" src="/docs/assets/img/new_lib_membership.png">

Como você pode ver que a data é formatada como ano-mês-dia, que é um formato de sistema. Para definir/mudar a data, hora e número de formatos, acesse

> Setup > Settings > System Settings

<img class="screenshot" alt="System Settings" src="/docs/assets/img/system_settings.png">

{next}
