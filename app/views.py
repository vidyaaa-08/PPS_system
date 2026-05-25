from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import render, redirect, resolve_url
from django.views.decorators.cache import never_cache
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import re

from django.contrib.auth.models import User

from django.contrib.auth import logout
# Create your views here.
from django.shortcuts import render
def dashboard(request):

    return render(
        request,
        'dashboard.html'
    ) 
from .models import Order, ProcessStep, calculate_end_date
from django.db.models import Sum
import math

def index(request):

    from datetime import timedelta
    import math

    status = request.GET.get('status')

    if status:
        orders = Order.objects.filter(status=status)
    else:
        orders = Order.objects.all()

    # Process Flow
    default_steps = [
        {'name': 'Order Generation', 'sla': 1},
        {'name': 'PPC Planning', 'sla': 0},
        {'name': 'CAD', 'sla': 7},
        {'name': 'CAM', 'sla': 2},
        {'name': 'Casting / Wax', 'sla': 2},
        {'name': 'Grading / OTECH', 'sla': 1.5},
        {'name': 'Filling', 'capacity': 10},
        {'name': 'Electro Polish', 'capacity': 15},
        {'name': 'Pre-Polish', 'capacity': 15},
        {'name': 'Diamond Bagging', 'sla': 0},
        {'name': 'Setting', 'capacity': 3000},
        {'name': 'Fitting', 'capacity': 10},
        {'name': 'Final Polish', 'capacity': 20},
        {'name': 'Rhodium', 'capacity': 20},
        {'name': 'Ceramic', 'capacity': 30},
        {'name': 'QA', 'capacity': 20},
        {'name': 'Hallmarking', 'sla': 1},
        {'name': 'Certification', 'sla': 0},
        {'name': 'FG (Finished)', 'sla': 0},
    ]

    orders = list(orders)

    for order in orders:

        # starting cursor for pipeline
        current = order.start_date

        # Overrides from DB
        steps_qs = ProcessStep.objects.filter(order=order)
        overrides = {p.process_name: p.sla_days for p in steps_qs}

        order.processes = []
        previous_end_date = None

        for step in default_steps:
            name = step['name']

            # Determine days
            if name == 'CAD':
                sla_value = 3 if getattr(order, 'style_type', 'New') == 'Repeat' else 7
                sla = overrides.get(name, sla_value)
                days = math.ceil(sla) if sla and sla > 0 else 0
            elif 'capacity' in step:
                capacity = step.get('capacity')
                if capacity and getattr(order, 'quantity', 0):
                    days = math.ceil(order.quantity / capacity)
                    if days <= 0 and order.quantity > 0:
                        days = 1
                else:
                    days = 0
                # override support
                sla_override = overrides.get(name)
                if sla_override is not None:
                    days = math.ceil(sla_override)
            else:
                sla = overrides.get(name, step.get('sla', 0))
                days = math.ceil(sla) if sla and sla > 0 else 0

            # If this step requires 0 days, it should happen on previous end_date (same day)
            # Otherwise start on current cursor.
            start_for_step = previous_end_date if (previous_end_date is not None and days == 0) else current

            # Calculate end_date for this step
            if days > 0:
                end_date = calculate_end_date(start_for_step, days)
            else:
                end_date = start_for_step

            order.processes.append({'name': name, 'computed_days': days, 'end_date': end_date})

            # update previous_end_date
            previous_end_date = end_date

            # compute next current: for 0-day steps remain on same day, else move to next working day
            if days == 0:
                current = end_date
            else:
                next_day = end_date + timedelta(days=1)
                if next_day.weekday() == 6:
                    next_day += timedelta(days=1)
                current = next_day

        # Final Expected Date
        order.final_expected = (
            order.processes[-1]['end_date']
            if order.processes
            else order.end_date
        )

        order.expected = order.final_expected

    context = {
        'orders': orders
    }

    return render(
        request,
        'index.html',
        context
    ) 

def logout_view(request):
    logout(request)
    return redirect('signin')

@never_cache
def sigin(request):
    """Custom login view matching the PPC design."""

    # Already logged in
    if request.user.is_authenticated:
        return redirect(resolve_url('dashboard'))

    if request.method == 'POST':

        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        # Manual Validation
        if not username:
            messages.error(request, 'Username is required.')
            return render(request, 'sigin.html', {
                'form': AuthenticationForm(),
                'next': request.GET.get('next', ''),
            })

        if len(username) < 3:
            messages.error(request, 'Username must be at least 3 characters.')
            return render(request, 'sigin.html', {
                'form': AuthenticationForm(),
                'next': request.GET.get('next', ''),
            })

        if not password:
            messages.error(request, 'Password is required.')
            return render(request, 'sigin.html', {
                'form': AuthenticationForm(),
                'next': request.GET.get('next', ''),
            })

        if len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
            return render(request, 'sigin.html', {
                'form': AuthenticationForm(),
                'next': request.GET.get('next', ''),
            })

        # Django Authentication Form
        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():

            user = form.get_user()
            login(request, user)

            # Remember Me
            if not request.POST.get('remember'):
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(1209600)  # 2 weeks

            # Success Message
            messages.success(
                request,
                f'Welcome back, {user.get_full_name() or user.username}!'
            )

            next_url = request.POST.get('next') or request.GET.get('next')

            return redirect(next_url or resolve_url('index'))

        else:
            # Detailed Errors
            if form.errors.get('username'):
                messages.error(request, 'Username does not exist.')

            elif form.errors.get('__all__'):
                messages.error(request, 'Invalid username or password.')

            else:
                messages.error(request, 'Login failed. Please try again.')

    else:
        form = AuthenticationForm()

    # Remember Username
    if not form.data:
        remembered = request.COOKIES.get('ppc_remember', '')
        if remembered:
            form = AuthenticationForm(initial={'username': remembered})

    return render(request, 'signin.html', {
        'form': form,
        'next': request.GET.get('next', ''),
    })

def register(request):

    if request.method == 'POST':

        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()

        # ================= VALIDATIONS =================

        # Username Validation
        if not username:
            messages.error(request, 'Username is required.')
            return redirect('register')

        if len(username) < 3:
            messages.error(request, 'Username must be at least 3 characters.')
            return redirect('register')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return redirect('register')

        # Email Validation
        if not email:
            messages.error(request, 'Email is required.')
            return redirect('register')

        email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'

        if not re.match(email_pattern, email):
            messages.error(request, 'Enter a valid email address.')
            return redirect('register')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return redirect('register')

        # Password Validation
        if not password:
            messages.error(request, 'Password is required.')
            return redirect('register')

        if len(password) < 6:
            messages.error(request, 'Password must be at least 6 characters.')
            return redirect('register')

        # Strong Password Validation
        if not re.search(r'[A-Z]', password):
            messages.error(request, 'Password must contain at least one uppercase letter.')
            return redirect('register')

        if not re.search(r'[a-z]', password):
            messages.error(request, 'Password must contain at least one lowercase letter.')
            return redirect('register')

        if not re.search(r'[0-9]', password):
            messages.error(request, 'Password must contain at least one number.')
            return redirect('register')

        # Confirm Password
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return redirect('register')

        # ================= CREATE USER =================

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        user.save()
        # Auto Login
        messages.success(request, 'Registration successful! Please login.')

        return redirect('signin')

    return render(request, 'register.html')

def base(request):
    return render(request, 'base.html')


def create_order(request):
    from .models import Order

    if request.method == 'POST':
        order_name = request.POST.get('order_name', '').strip()
        order_type = request.POST.get('order_type')
        category = request.POST.get('category')
        quantity = int(request.POST.get('quantity') or 0)
        start_date = request.POST.get('start_date')
        style_type = request.POST.get('style_type', 'New')

        if not order_name or not order_type or not category or not start_date or quantity <= 0:
            messages.error(request, 'Please enter all required fields correctly.')
            return render(request, 'create_order.html')

        # Create order without end_date so signals can compute it automatically
        order = Order.objects.create(
            order_no=order_name,
            order_type=order_type,
            category=category,
            quantity=quantity,
            start_date=start_date,
            style_type=style_type,
        )

        messages.success(request, f'Order {order.order_no} created.')
        return redirect('index')

    # Provide choice lists for the form selects
    context = {
        'order_types': Order.ORDER_TYPES,
        'categories': Order.CATEGORY_TYPES,
        'style_types': Order.STYLE_TYPE_CHOICES,
    }
    return render(request, 'create_order.html', context)
def forgot(request):

    if request.method == "POST":

        username = request.POST.get("username")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        try:
            user = User.objects.get(username=username)

        except User.DoesNotExist:
            messages.error(request, "Username not found.")
            return redirect("forgot")

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("forgot")

        user.set_password(new_password)
        user.save()

        messages.success(request, "Password updated successfully.")
        return redirect("signin")

    return render(request, "forgot.html")