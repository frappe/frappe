# Form Client Scripting

## Escrevendo script de formulários

Até agora nós criamos um sistema básico que funciona fora da caixa, sem ter que escrever nenhum código. Vamos agora escrever alguns scripts para tornar a aplicação mais rica e adicionar validações de formulários para o usuário não inserir dados incorretos.

### Script no Lado do Cliente

No DocType **Library Transaction**, temos um único campo de nome do membro. Não fizemos dois campos. Agora, isso poderia muito bem ser dois campos (e provavelmente deve), mas por uma questão de exemplo, vamos considerar que temos que implementar isto. Para fazer isso, teria que escrever um Handler de eventos para um evento para quando o usuário selecionar o campo `library_member`, acessar o recurso membro do servidor usando REST API e inserir os valores no formulário.

Para iniciar o script, na pasta `library_management/doctype/library_transaction`, crie um novo arquivo `library_transaction.js`. Este arquivo será executado automaticamente quando a primeiro Library Transaction for aberta pelo usuário. Portanto, neste arquivo, podemos ligar os eventos e escrever outras funções.

#### library_transaction.js

	frappe.ui.form.on("Library Transaction", "library_member",
		function(frm) {
			frappe.call({
				"method": "frappe.client.get",
				args: {
					doctype: "Library Member",
					name: frm.doc.library_member
				},
				callback: function (data) {
					frappe.model.set_value(frm.doctype,
						frm.docname, "member_name",
						data.message.first_name
						+ (data.message.last_name ?
							(" " + data.message.last_name) : ""))
				}
			})
		});

1. **frappe.ui.form.on(*doctype*, *fieldname*, *handler*)** é utilizado para ligar um handler ao evento quando a propriedade library_member for definida.
1. No handler, nós desencadear uma chamada AJAX para `frappe.client.get`. Em resposta obtemos o objeto solicitado como JSON. [Saiba mais sobre a API](/frappe/user/en/guides/integration/rest_api).
1. Utilizando **frappe.model.set_value(*doctype*, *name*, *fieldname*, *value*)** Nós inserimos o valor no formulário.

**Observação:** Para verificar se o script funciona, lembre-se de 'recarregar' a página antes de testar seu script. mudanças no script do cliente não são captadas automaticamente quando você está no modo de desenvolvedor..

{next}
