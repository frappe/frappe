"""
	Jinja2 markdown2 extension
	by Silas Swell
	http://www.silassewell.com/blog/2010/05/10/jinja2-markdown-extension/
"""

import jinja2
import jinja2.ext
import markdown2

class Markdown2Extension(jinja2.ext.Extension):
    tags = set(['markdown2'])

    def __init__(self, environment):
        super(Markdown2Extension, self).__init__(environment)
        environment.extend(
            markdowner=markdown2.Markdown()
        )   

    def parse(self, parser):
        lineno = parser.stream.next().lineno
        body = parser.parse_statements(
            ['name:endmarkdown2'],
            drop_needle=True
        )
        return jinja2.nodes.CallBlock(
            self.call_method('_markdown_support'),
            [],
            [],
            body
        ).set_lineno(lineno)

    def _markdown_support(self, caller):
        return self.environment.markdowner.convert(caller()).strip()