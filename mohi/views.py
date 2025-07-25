from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from .decorators import is_staff_required
from .models import CustomUser, Loan, Repayment

def home(request):
    return render(request, 'mohi/home.html')


def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            return render(request, 'mohi/login.html', {'error': 'Invalid email or password.'})
    return render(request, 'mohi/login.html')

def logout_view(request):
    logout(request)
    return redirect('/')

@is_staff_required
def register(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        department = request.POST.get('department')
        designation = request.POST.get('designation')
        password = request.POST.get('password')

        if not all([first_name, last_name, email, department, designation, password]):
            return render(request, 'mohi/register.html', {'error': 'All fields are required.'})

        if CustomUser.objects.filter(email=email).exists():
            return render(request, 'mohi/register.html', {'error': 'Email already exists.'})

        user = CustomUser.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=email,
            department=department,
            designation=designation,
            password=make_password(password),
            is_staff=False,
            is_active=True
        )
        user.save()
        return redirect('home')

    return render(request, 'mohi/register.html')

@login_required
def apply_loan(request):
    if request.method == 'POST':
        amount = request.POST.get('amount')
        term_months = request.POST.get('term_months')
        user = request.user

        try:
            amount = float(amount)
            term_months = int(term_months)
            if amount <= 0 or term_months <= 0:
                raise ValueError
        except ValueError:
            return render(request, 'mohi/loan_apply.html', {'error': 'Invalid amount or term.'})

        start_date = timezone.now().date()
        end_date = start_date + timedelta(days=30 * term_months)

        loan = Loan.objects.create(
            user=user,
            amount=amount,
            term_months=term_months,
            start_date=start_date,
            end_date=end_date,
            balance=amount,
            is_paid=False
        )
        loan.save()

        return redirect('loan_list')

    return render(request, 'mohi/loan_apply.html')

@login_required
def loan_list(request):
    loans = Loan.objects.filter(user=request.user)
    return render(request, 'mohi/loan_list.html', {'loans': loans})

@login_required
def loan_detail(request, loan_id):
    loan = get_object_or_404(Loan, id=loan_id, user=request.user)
    schedule = loan.generate_amortization_schedule()
    repayments = Repayment.objects.filter(loan=loan)
    return render(request, 'mohi/loan_detail.html', {'loan': loan, 'schedule': schedule, 'repayments': repayments})

@login_required
def make_repayment(request, loan_id):
    loan = get_object_or_404(Loan, id=loan_id, user=request.user)
    if request.method == 'POST':
        amount = request.POST.get('amount')
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError
            if amount > float(loan.balance):
                return render(request, 'mohi/make_repayment.html', {'loan': loan, 'error': 'Repayment amount exceeds loan balance.'})
        except ValueError:
            return render(request, 'mohi/make_repayment.html', {'loan': loan, 'error': 'Invalid repayment amount.'})

        monthly_rate = float(loan.interest_rate) / 100
        interest = float(loan.balance) * monthly_rate
        principal = min(amount, float(loan.balance) - interest)
        if principal < 0:
            principal = 0
            interest = amount

        with transaction.atomic():
            repayment = Repayment.objects.create(
                loan=loan,
                date=timezone.now().date(),
                amount=amount,
                principal=principal,
                interest=interest
            )
            loan.balance -= amount
            if loan.balance <= 0:
                loan.balance = 0
                loan.is_paid = True
                loan.end_date = timezone.now().date()
            loan.save()
            repayment.save()

        return redirect('loan_list')

    return render(request, 'mohi/make_repayment.html', {'loan': loan})

@is_staff_required
def loan_report(request):
    total_loans = Loan.objects.aggregate(total=Sum('amount'))['total'] or 0
    total_repayments = Repayment.objects.aggregate(total=Sum('amount'))['total'] or 0
    return render(request, 'mohi/loan_report.html', {'total_loans': total_loans, 'total_repayments': total_repayments})