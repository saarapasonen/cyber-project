from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.db import connection
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from .forms import PinForm, TimeEntryForm
from .models import Profile, TimeEntry


def register(request):
    errors = []
    username = ''
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password1', '')
        confirm = request.POST.get('password2', '')

        if not username:
            errors.append('Username is required.')
        elif User.objects.filter(username=username).exists():
            errors.append('That username is already taken.')
        if password != confirm:
            errors.append('The two password fields did not match.')

        # === FLAW 5: A07 Identification and Authentication Failures ===
        # The view does NOT call password_validation.validate_password().
        # Combined with AUTH_PASSWORD_VALIDATORS = [] in
        # worklog/settings.py, there is no enforcement anywhere — a user
        # can register with "1", "abc", "password", "12345", etc.
        # See README section "Reproducing Flaw 5" for steps.

        # === FIX (commented out — uncomment to apply) ===
        # Run Django's configured password validators against the chosen
        # password (re-enable them in worklog/settings.py at the same
        # time) and surface their messages back to the form.
        # from django.contrib.auth.password_validation import validate_password
        # from django.core.exceptions import ValidationError
        # try:
        #     validate_password(password, User(username=username))
        # except ValidationError as exc:
        #     errors.extend(exc.messages)

        if not errors:
            user = User(username=username)
            user.set_password(password)
            user.save()
            Profile.objects.create(user=user)
            login(request, user)
            return redirect('entry_list')
    return render(
        request,
        'tracker/register.html',
        {'errors': errors, 'username': username},
    )


@login_required
def entry_list(request):
    query = request.GET.get('q', '').strip()
    if query:
        # === FLAW 3: A03 Injection (SQL injection) ===
        # The search term is interpolated directly into the SQL string with
        # an f-string — no parameterization, no escaping. A payload that
        # closes the LIKE pattern and comments out the trailing WHERE
        # clauses (e.g. `%') OR 1=1 -- `) makes the query return rows that
        # do not belong to the current user.
        # See README section "Reproducing Flaw 3" for steps.
        sql = (
            "SELECT id, owner_id, project, hours, description, date "
            "FROM tracker_timeentry "
            f"WHERE owner_id = {request.user.id} "
            f"AND (project LIKE '%{query}%' OR description LIKE '%{query}%') "
            "ORDER BY date DESC, id DESC"
        )
        with connection.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
        entries = [
            TimeEntry(
                id=r[0], owner_id=r[1], project=r[2],
                hours=r[3], description=r[4], date=r[5],
            )
            for r in rows
        ]

        # === FIX (commented out — uncomment to apply) ===
        # Preferred: use the ORM, which always parameterizes.
        # entries = TimeEntry.objects.filter(owner=request.user).filter(
        #     Q(project__icontains=query) | Q(description__icontains=query)
        # )
        #
        # Or, if raw SQL is required, pass parameters separately so the
        # database driver escapes them:
        # like = f'%{query}%'
        # with connection.cursor() as cursor:
        #     cursor.execute(
        #         "SELECT id, owner_id, project, hours, description, date "
        #         "FROM tracker_timeentry WHERE owner_id = %s "
        #         "AND (project LIKE %s OR description LIKE %s) "
        #         "ORDER BY date DESC, id DESC",
        #         [request.user.id, like, like],
        #     )
        #     rows = cursor.fetchall()
        # entries = [
        #     TimeEntry(id=r[0], owner_id=r[1], project=r[2],
        #               hours=r[3], description=r[4], date=r[5])
        #     for r in rows
        # ]
    else:
        entries = TimeEntry.objects.filter(owner=request.user)
    return render(
        request,
        'tracker/entry_list.html',
        {'entries': entries, 'query': query},
    )


@login_required
def entry_create(request):
    if request.method == 'POST':
        form = TimeEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.owner = request.user
            entry.save()
            return redirect('entry_list')
    else:
        form = TimeEntryForm()
    return render(request, 'tracker/entry_form.html', {'form': form, 'mode': 'Create'})


@login_required
def entry_detail(request, pk):
    # === FLAW 1: A01 Broken Access Control (IDOR) ===
    # The line below fetches a TimeEntry by primary key only, with no
    # ownership check. Any logged-in user can read any other user's entry
    # just by editing the integer in the URL (/1/, /2/, /3/, ...).
    # See README section "Reproducing Flaw 1" for steps.
    entry = get_object_or_404(TimeEntry, pk=pk)

    # === FIX (commented out — uncomment to apply) ===
    # Scope the lookup to the owning user so a missing/foreign pk returns 404.
    # entry = get_object_or_404(TimeEntry, pk=pk, owner=request.user)

    return render(request, 'tracker/entry_detail.html', {'entry': entry})


@login_required
def entry_edit(request, pk):
    # === FLAW 1: A01 Broken Access Control (IDOR) ===
    # Same flaw as entry_detail — no ownership check, so any logged-in user
    # can EDIT any other user's entry by tampering with the URL.
    # See README section "Reproducing Flaw 1" for steps.
    entry = get_object_or_404(TimeEntry, pk=pk)

    # === FIX (commented out — uncomment to apply) ===
    # entry = get_object_or_404(TimeEntry, pk=pk, owner=request.user)

    if request.method == 'POST':
        form = TimeEntryForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            return redirect('entry_detail', pk=entry.pk)
    else:
        form = TimeEntryForm(instance=entry)
    return render(request, 'tracker/entry_form.html', {'form': form, 'mode': 'Edit'})


@login_required
def entry_delete(request, pk):
    entry = get_object_or_404(TimeEntry, pk=pk, owner=request.user)
    profile, _ = Profile.objects.get_or_create(user=request.user)
    error = None
    if request.method == 'POST':
        submitted_pin = request.POST.get('pin', '')
        # NOTE: Profile.check_pin() is the flawed part (plaintext comparison
        # in tracker/models.py — Flaw 2). The view calls it the same way
        # regardless of whether the model stores the PIN hashed or plaintext.
        if profile.pin and profile.check_pin(submitted_pin):
            entry.delete()
            return redirect('entry_list')
        error = 'Incorrect or unset PIN. Set one at /profile/pin/ first.'
    return render(
        request,
        'tracker/entry_confirm_delete.html',
        {'entry': entry, 'error': error},
    )


@login_required
def profile_pin(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = PinForm(request.POST)
        if form.is_valid():
            profile.set_pin(form.cleaned_data['pin'])
            profile.save()
            return redirect('entry_list')
    else:
        form = PinForm()
    return render(request, 'tracker/profile_pin.html', {'form': form})


def debug_error(request):
    # NOTE: This view is a *demo trigger* used to reproduce Flaw 4.
    # In a real codebase an unhandled exception like this would normally
    # happen by accident (KeyError, ZeroDivisionError, ...). The flaw
    # itself lives in worklog/settings.py (DEBUG=True + ALLOWED_HOSTS=['*']
    # + hardcoded SECRET_KEY) — it's what makes the resulting error page
    # leak settings, environment, and the SECRET_KEY to anyone who can
    # cause an exception.
    raise RuntimeError('Intentional crash to reproduce Flaw 4 (A05).')


@user_passes_test(lambda u: u.is_authenticated and u.is_staff)
def team_summary(request):
    totals = (
        TimeEntry.objects.values('owner__username')
        .annotate(total_hours=Sum('hours'))
        .order_by('owner__username')
    )
    return render(request, 'tracker/team_summary.html', {'totals': totals})
