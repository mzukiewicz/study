import os
from django.db import models
from django.core import validators
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import PermissionsMixin, AbstractBaseUser
from django.contrib.auth.signals import user_logged_in
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.conf import settings
from . import managers
from . import storage


def add_logged_in_log(sender, user, **kwargs):
    user.add_log_entry(_("User has been successfully logged in."))
user_logged_in.connect(add_logged_in_log)


class UserProfile(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(
        _("Email"),
        unique=True,
        null=False,
        blank=False,
    )
    username = models.CharField(
        _("Name"),
        max_length=64,
        null=False,
        blank=False,
        help_text=_("Required. 64 characters or fewer. May contain letters and digits."),
        validators=[
            validators.RegexValidator(r'^[a-zA-Z0-9.@-_ ]+$',
                                      _("Valid name may contain letters and digits."))
        ]
    )
    registration_date = models.DateTimeField(
        _("Registration date"),
        auto_now_add=True,
        blank=False,
        null=False,
    )
    registration_ip = models.GenericIPAddressField(
        _("IP Address"),
        blank=True,
        null=True,
    )
    is_active = models.BooleanField(
        _("Active"),
        blank=False,
        null=False,
        default=False,
    )
    is_staff = models.BooleanField(
        _("Staff"),
        blank=False,
        null=False,
        default=False,
    )

    objects = managers.UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = _("User profile")
        verbose_name_plural = _("User profiles")

    def get_short_name(self):
        return self.username

    def get_full_name(self):
        return self.username

    def add_log_entry(self, message, **kwargs):
        log_entry = UserLogEntry.objects.add_entry(self, message, **kwargs)
        return log_entry


class UserLogEntry(models.Model):
    user = models.ForeignKey(
        UserProfile,
        verbose_name=_("User"),
        related_name='log_entries',
        related_query_name='log_entry',
        blank=False,
        null=False,
        on_delete=models.CASCADE,
    )
    date_added = models.DateTimeField(
        _("Date added"),
        blank=False,
        null=False,
        auto_now_add=True,
    )
    type = models.CharField(
        _("Type"),
        max_length=16,
        choices=(
            ('general', _("General")),
            ('user', _("User")),
            ('error', _("Error")),
        ),
        blank=False,
        null=False,
        default='general',
    )
    message = models.CharField(
        _("Message"),
        max_length=255,
        blank=False,
        null=False,
    )

    objects = managers.UserLogEntryManager()

    class Meta:
        verbose_name = _("User log entry")
        verbose_name_plural = _("User log entries")

    def __str__(self):
        return self.message


class UserSession(models.Model):
    user = models.ForeignKey(
        UserProfile,
        verbose_name=_("User"),
        related_name='session_references',
        related_query_name='session_reference',
        blank=False,
        null=False,
    )
    session_key = models.CharField(
        _("Session key"),
        max_length=40,
        blank=False,
        null=False,
    )

    class Meta:
        verbose_name = _("User session reference")
        verbose_name_plural = _("User session references")

    def delete_user_session(self):
        Session.objects.filter(session_key=self.session_key).delete()
        self.delete()


def avatar_path(instance, filename):
    return 'user/avatars/%i.jpg' % instance.pk


class UserAvatar(models.Model):
    user = models.OneToOneField(
        UserProfile,
        verbose_name=_("User"),
        related_name='avatar',
        related_query_name='avatar',
        blank=False,
        null=False,
    )
    picture = models.ImageField(
        _("Picture"),
        default=None,
        blank=True,
        null=True,
        storage=storage.OverwriteStorage(),
        upload_to=avatar_path,
    )
    last_update = models.DateTimeField(
        _("Last update"),
        default=None,
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = _("Avatar")
        verbose_name_plural = _("Avatars")

    def can_update(self, time=None):
        if self.last_update is None:
            return True

        if not time:
            time = timezone.timedelta(minutes=15)

        now = timezone.now()
        return self.last_update.time() + time < now

    def update_avatar(self, content_file):
        self.picture.save('%i.jpg' % self.pk, content_file)
        self.last_update = timezone.now()
        self.save(update_fields=['picture', 'last_update'])
