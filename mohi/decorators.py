from django.http import HttpResponseForbidden
from django.shortcuts import redirect

def is_staff_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')  # Redirect to login if not authenticated
        if not request.user.is_staff:
            return HttpResponseForbidden("You must be a staff member to access this page.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view