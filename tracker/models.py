from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
from django.db import models


class TimeEntry(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='time_entries',
    )
    project = models.CharField(max_length=120)
    hours = models.DecimalField(max_digits=5, decimal_places=2)
    description = models.TextField(blank=True)
    date = models.DateField()

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f'{self.project} ({self.hours}h on {self.date})'


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    pin = models.CharField(max_length=128, blank=True)

    # === FLAW 2: A02 Cryptographic Failures ===
    # The PIN is stored as cleartext in the database. Anyone with read
    # access to db.sqlite3 (e.g. a leaked backup, the Django admin page,
    # or `sqlite3 db.sqlite3 "select * from tracker_profile;"`) sees the
    # raw PIN value. There is no hashing, no salting, no work factor.
    # See README section "Reproducing Flaw 2" for steps.
    def set_pin(self, raw_pin):
        self.pin = raw_pin  # plaintext

    def check_pin(self, raw_pin):
        return self.pin == raw_pin  # plaintext comparison

    # === FIX (commented out — uncomment to apply) ===
    # Hash the PIN with Django's password hashers (PBKDF2 by default), and
    # use constant-time comparison via check_password. Replace each method
    # above with its hashed counterpart below.
    # def set_pin(self, raw_pin):
    #     self.pin = make_password(raw_pin)
    #
    # def check_pin(self, raw_pin):
    #     return check_password(raw_pin, self.pin)

    def __str__(self):
        return f'Profile<{self.user.username}>'
