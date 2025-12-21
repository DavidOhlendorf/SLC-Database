from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

class EditorRequiredMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """
    Require the global 'Editor' permission for any write action.
    """
    permission_required = "accounts.can_edit_slc"
    raise_exception = True  # -> 403 
