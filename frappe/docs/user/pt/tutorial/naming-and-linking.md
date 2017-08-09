# Nomeando e vinculando DocType

Em seguida, vamos criar outro DocType e salva-lo também:

1. Library Member (First Name, Last Name, Email Address, Phone, Address)

<img class="screenshot" alt="Doctype Saved" src="/docs/assets/img/naming_doctype.png">


#### Nomeação de DocTypes

DocTypes podem ser nomeados de diferentes formas:

1. Com base em um campo
1. Com base numa série
1. Pelo controlador (Código)
1. Prompt

Isso pode ser definido através do preenchimento do campo **Autoname**. Para o controlador, deixe em branco.

> **Search Fields**: A DocType pode ser nomeado em uma série, mas ele ainda precisa ser pesquisado por nome. No nosso caso, o artigo será procurado pelo título ou o nome do autor. Portanto, este pode ser inserido no campo de pesquisa.

<img class="screenshot" alt="Autonaming and Search Field" src="/docs/assets/img/autoname_and_search_field.png">

#### Vinculando e selecionando campos

As chaves estrangeiras são especificados no Frappé como um tipo de campo **Link**. O DocType alvo deve ser mencionado na área de Opções de texto.

No nosso exemplo, na Library Transaction DocType, temos que ligar o Membro da Biblioteca e o artigo.

**Observação:** Lembre-se que os campos link não são automaticamente configurados como chaves estrangeiras no banco de dados MariaDB, porque isso vai implicitamente indexar a coluna. Isto pode não ser ideal, mas, a validação de chave estrangeira é feito pelo Framework.

<img class="screenshot" alt="Link Field" src="/docs/assets/img/link_field.png">

Para campos de multipla escolha, como mencionamos anteriormente, adicione as várias opções na caixa de entrada **Options**, cada opção em uma nova linha.

<img class="screenshot" alt="Select Field" src="/docs/assets/img/select_field.png">

Fazer o mesmo para outros modelos.

#### Vinculando valores

Um modelo padrão é quando você seleciona um ID, **Library Member** na **Library Membership**, então, o primeiro e o ultimo nome dos membros devem ser copiados para os campos adequados ao gravar na Library Membership Transaction.

Para fazer isso, podemos usar campos de somente leitura e de opções, podemos definir o nome do link e o nome do campo da propriedade que deseja buscar. Para este exemplo no **Member First Name** podemos definir `library_member.first_name`

<img class="screenshot" alt="Fetch values" src="/docs/assets/img/fetch.png">

### Complete os modelos

Da mesma forma, você pode completar todos os modelos de modo que os campos finais fiquem parecido com este:

#### Article

<img class="screenshot" alt="Article" src="/docs/assets/img/doctype_article.png">

#### Library Member

<img class="screenshot" alt="Library Member" src="/docs/assets/img/doctype_lib_member.png">

#### Library Membership

<img class="screenshot" alt="Library Membership" src="/docs/assets/img/doctype_lib_membership.png">

#### Library Transaction

<img class="screenshot" alt="Library Transaction" src="/docs/assets/img/doctype_lib_trans.png">

> Lembre-se de dar permissões para **Librarian** em cada DocType

{next}
