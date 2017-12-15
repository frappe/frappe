# Controladores

O passo seguinte seria a adição de métodos e handlers de eventos para os modelos. No aplicativo, devemos assegurar que se uma Library Transaction é feita, o artigo em questão deve estar em estoque e o membro que irá emprestar o artigo deve ter um filiação válida.

Para isso, podemos escrever uma validação pouco antes do objeto de Library Transaction ser salvo. Para fazer isso, abra o template `library_management/doctype/library_transaction/library_transaction.py`.

Este arquivo é o controlador para o objeto Library Transaction. Nele você pode escrever métodos para:

1. `before_insert`
1. `validate` (antes de inserir ou atualizar)
1. `on_update` (depois de salvar)
1. `on_submit` (quando o documento é submetido)
1. `on_cancel`
1. `on_trash` (antes que ele esteja prestes a ser excluido)

Você pode escrever métodos para esses eventos e eles serão chamados pelo framework quando o documento for salvo etc.

Aqui é o controlador acabado:

	from __future__ import unicode_literals
	import frappe
	from frappe import _
	from frappe.model.document import Document

	class LibraryTransaction(Document):
		def validate(self):
			last_transaction = frappe.get_list("Library Transaction",
				fields=["transaction_type", "transaction_date"],
				filters = {
					"article": self.article,
					"transaction_date": ("<=", self.transaction_date),
					"name": ("!=", self.name)
				})
			if self.transaction_type=="Issue":
				msg = _("Article {0} {1} has not been recorded as returned since {2}")
				if last_transaction and last_transaction[0].transaction_type=="Issue":
					frappe.throw(msg.format(self.article, self.article_name,
						last_transaction[0].transaction_date))
			else:
				if not last_transaction or last_transaction[0].transaction_type!="Issue":
					frappe.throw(_("Cannot return article not issued"))

Nesse script:

1. Pegamos a última transação antes da data da transação atual usando a função de consulta `frappe.get_list`
1. Se a última transação for algo que não queremos, lançamos uma exceção usando `frappe.throw`
1. Usamos o método `_("text")` para identificar strings traduzíveis.

Verifique se suas validações funcionaram, criando de novos registros.

<img class="screenshot" alt="Transaction" src="/docs/assets/img/lib_trans.png">

#### Debugging

Para Debugar, mantenha sempre o seu Console JS aberto. procurando por erros de servidor e JavaScript.

Além disso, verifique a sua janela do terminal para exceções. Quaisquer  **500 Internal Server Errors** será impresso em seu terminal, onde o servidor está rodando.

{next}
