from django import forms

from .models import TimeEntry


class TimeEntryForm(forms.ModelForm):
    class Meta:
        model = TimeEntry
        fields = ('project', 'hours', 'description', 'date')
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class PinForm(forms.Form):
    pin = forms.CharField(
        max_length=32,
        widget=forms.PasswordInput,
        label='Confirm with your PIN',
    )
