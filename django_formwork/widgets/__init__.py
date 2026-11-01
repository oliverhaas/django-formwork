"""Custom form widgets for django-formwork.

All widgets are importable from ``django_formwork.widgets``::

    from django_formwork.widgets import Toggle, Select, DatePicker
"""

from django_formwork.widgets.checkbox import CheckboxInput
from django_formwork.widgets.combo_box import ComboBox, ComboBoxMultiple
from django_formwork.widgets.datalist import DataList
from django_formwork.widgets.date_picker import DatePicker
from django_formwork.widgets.file_drop_zone import FileDropZone
from django_formwork.widgets.floating import Textarea, TextInput
from django_formwork.widgets.image_drop_zone import ImageDropZone
from django_formwork.widgets.input_mask import InputMask
from django_formwork.widgets.input_number import InputNumber
from django_formwork.widgets.otp_input import OTPInput
from django_formwork.widgets.password_reveal import PasswordReveal
from django_formwork.widgets.range import Range
from django_formwork.widgets.rating import Rating
from django_formwork.widgets.search_input import SearchInput
from django_formwork.widgets.select import ChoiceLabel, Select
from django_formwork.widgets.select_multiple import SelectMultiple
from django_formwork.widgets.toggle import Toggle
from django_formwork.widgets.validated_textarea import ValidatedTextarea

__all__ = [
    "CheckboxInput",
    "ChoiceLabel",
    "ComboBox",
    "ComboBoxMultiple",
    "DataList",
    "DatePicker",
    "FileDropZone",
    "ImageDropZone",
    "InputMask",
    "InputNumber",
    "OTPInput",
    "PasswordReveal",
    "Range",
    "Rating",
    "SearchInput",
    "Select",
    "SelectMultiple",
    "TextInput",
    "Textarea",
    "Toggle",
    "ValidatedTextarea",
]
