"""Django's ``makemessages``, which reads a template in a ``jinja2`` directory with Jinja's own parser.

Django reads every template with its own lexer, which finds no text in a Jinja ``{% trans %}`` block
or in a ``_()`` call with arguments.
"""

from __future__ import annotations

from pathlib import Path

import jinja2
from django.core.management.commands import makemessages
from jinja2.ext import extract_from_ast

# The extensions of formwork's environments. Jinja cannot parse a template that needs
# another one, so that template is read as a Django template.
_ENVIRONMENT = jinja2.Environment(extensions=["jinja2.ext.i18n", "jinja2.ext.do", "jinja2.ext.loopcontrols"])  # noqa: S701 (never renders)

# The gettext function that xgettext reads for each Jinja name, and how many leading
# string arguments it reads.
_FUNCTIONS = {
    "_": ("gettext", 1),
    "gettext": ("gettext", 1),
    "ngettext": ("ngettext", 2),
    "pgettext": ("pgettext", 2),
    "npgettext": ("npgettext", 3),
}


class BuildFile(makemessages.BuildFile):
    def preprocess(self) -> None:
        if self.domain != "django" or not self.is_templatized or "jinja2" not in Path(self.path).parts[:-1]:
            super().preprocess()
            return
        source = Path(self.path).read_text(encoding="utf-8")
        try:
            found = list(extract_from_ast(_ENVIRONMENT.parse(source), tuple(_FUNCTIONS)))
        except jinja2.TemplateSyntaxError as error:
            self.command.stderr.write(f"Jinja cannot parse {self.path} ({error}); it is read as a Django template.")
            super().preprocess()
            return
        # Each gettext call as Python, on the line of the template it comes from.
        lines: list[list[str]] = [[] for _ in range(source.count("\n") + 1)]
        for lineno, name, message in found:
            function, count = _FUNCTIONS[name]
            strings = (message if isinstance(message, tuple) else (message,))[:count]
            if len(strings) == count and all(isinstance(string, str) for string in strings):
                # The number of a plural is a dummy; xgettext reads only the strings.
                arguments = [repr(string) for string in strings] + (["0"] if function.startswith("n") else [])
                lines[lineno - 1].append(f"{function}({', '.join(arguments)})")
        content = "\n".join("; ".join(calls) for calls in lines) + "\n"
        Path(self.work_path).write_text(content, encoding="utf-8")


class Command(makemessages.Command):
    build_file_class = BuildFile
