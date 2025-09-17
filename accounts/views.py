from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages


def loginpage(request):

    if request.method == 'POST':
        user = request.POST.get('user')
        password = request.POST.get('password')

        user = authenticate(request, username=user, password=password)

        if user is not None:
            login(request, user)
            return redirect('search')
        else:
            messages.error(request, 'Benutzername oder Passwort falsch')

    return render(request, 'accounts/login.html',)
    
