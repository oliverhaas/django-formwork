"""Custom form widgets for django-formwork.

All widgets are importable from ``django_formwork.widgets``::

    from django_formwork.widgets import Toggle, SearchSelect, DatePicker
"""

from django_formwork.widgets.combo_box import ComboBox
from django_formwork.widgets.datalist import DataList
from django_formwork.widgets.date_picker import DatePicker
from django_formwork.widgets.file_drop_zone import FileDropZone
from django_formwork.widgets.floating import Select, TextInput, Textarea
from django_formwork.widgets.image_drop_zone import ImageDropZone
from django_formwork.widgets.input_mask import InputMask
from django_formwork.widgets.input_number import InputNumber
from django_formwork.widgets.multi_select import MultiSelect
from django_formwork.widgets.otp_input import OTPInput
from django_formwork.widgets.password_reveal import PasswordReveal
from django_formwork.widgets.range import Range
from django_formwork.widgets.rating import Rating
from django_formwork.widgets.search_select import SearchSelect
from django_formwork.widgets.toggle import Toggle
from django_formwork.widgets.validated_textarea import ValidatedTextarea

__all__ = [
    "ComboBox",
    "DataList",
    "DatePicker",
    "FileDropZone",
    "ImageDropZone",
    "InputMask",
    "InputNumber",
    "MultiSelect",
    "OTPInput",
    "PasswordReveal",
    "Range",
    "Rating",
    "SearchSelect",
    "Select",
    "TextInput",
    "Textarea",
    "Toggle",
    "ValidatedTextarea",
]
