from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth import login
from django.views.generic import CreateView
from django.urls import reverse_lazy

from accounts.forms import CustomAuthenticationForm, CustomUserCreationForm

class AccountLogin(LoginView):
    form_class = CustomAuthenticationForm
    template_name = 'accounts/login.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        return context
    
    def get_success_url(self):
        url = self.get_redirect_url()
        if url:
            return url
        else:
            return reverse_lazy("PetriNET:main_map")


class AccountLogout(LogoutView):
    next_page = reverse_lazy('PetriNET:main_map')


class AccountRegister(CreateView):
    form_class = CustomUserCreationForm
    template_name = 'accounts/registration.html'
    success_url = reverse_lazy('PetriNET:main_map')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        return context

    def post(self, *args, **kwargs):
        response = super().post(*args, **kwargs)
        if self.object:
            self.object.is_superuser = True
            login(self.request, self.object)

        return response
