"""Project-local widgets for the task manager example."""

from django import forms

# A short dial-code list for the demo. A real project would source this from a
# phone library rather than hand-maintaining flags and codes.
DIAL_CODES = [
    ("+1", "🇺🇸 +1"),
    ("+44", "🇬🇧 +44"),
    ("+49", "🇩🇪 +49"),
    ("+33", "🇫🇷 +33"),
    ("+34", "🇪🇸 +34"),
    ("+39", "🇮🇹 +39"),
    ("+31", "🇳🇱 +31"),
    ("+46", "🇸🇪 +46"),
    ("+61", "🇦🇺 +61"),
    ("+81", "🇯🇵 +81"),
    ("+91", "🇮🇳 +91"),
    ("+55", "🇧🇷 +55"),
]


class PhoneInput(forms.MultiWidget):
    """Dial-code selector joined to a phone number input.

    The submitted value is ``"{dial_code} {number}"`` (e.g. ``"+1 5551234"``).
    Usage: ``forms.CharField(widget=PhoneInput)``.
    """

    template_name = "taskmanager/widgets/phone_input.html"

    def __init__(self, attrs=None, *, default_dial_code="+1"):
        self.default_dial_code = default_dial_code
        self.dial_code_choices = DIAL_CODES
        super().__init__(
            widgets=[
                forms.HiddenInput(),
                forms.TextInput(
                    attrs={"placeholder": "Phone number", "type": "tel", "class": "join-item input grow"},
                ),
            ],
            attrs=attrs,
        )

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["dial_code_choices"] = self.dial_code_choices
        return context

    def decompress(self, value):
        if not value:
            return [self.default_dial_code, ""]
        head, sep, tail = value.partition(" ")
        return [head, tail] if sep else [self.default_dial_code, head]

    def value_from_datadict(self, data, files, name):
        values = super().value_from_datadict(data, files, name)
        dial_code = values[0] or ""
        number = values[1] or ""
        return f"{dial_code} {number}".strip() if number else ""
