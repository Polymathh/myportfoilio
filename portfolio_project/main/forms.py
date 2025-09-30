from django import forms
from .models import Contact

class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ["name", "phone", "email", "subject", "message"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Name", "class": "input"}),
            "phone": forms.TextInput(attrs={"placeholder": "Phone No", "class": "input"}),
            "email": forms.EmailInput(attrs={"placeholder": "Email", "class": "input"}),
            "subject": forms.TextInput(attrs={"placeholder": "Subject", "class": "input"}),
            "message": forms.Textarea(attrs={"placeholder": "Message", "class": "textarea", "rows": 8}),
        }