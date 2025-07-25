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
from datetime import datetime as dt
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from .decorators import is_staff_required
from .models import CustomUser, Loan, Repayment
import logging
import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
import subprocess
import os
from django.conf import settings


def home(request):
    return render(request, 'mohi/home.html')

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
        try:
            amount = float(amount)
            term_months = int(term_months)
            if amount <= 0 or term_months <= 0:
                raise ValueError
        except ValueError:
            return render(request, 'mohi/loan_apply.html', {'error': 'Invalid amount or term.'})

        if request.user.is_staff:
            user_id = request.POST.get('user_id')
            user = get_object_or_404(CustomUser, id=user_id)
        else:
            user = request.user

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

    users = CustomUser.objects.all() if request.user.is_staff else None
    return render(request, 'mohi/loan_apply.html', {'users': users})


@is_staff_required
def issue_loan(request):
    if request.method == 'POST':
        amount = request.POST.get('amount')
        term_months = request.POST.get('term_months')
        try:
            amount = float(amount)
            term_months = int(term_months)
            if amount <= 0 or term_months <= 0:
                raise ValueError
        except ValueError:
            return render(request, 'mohi/issue_loan.html', {'error': 'Invalid amount or term.', 'users': CustomUser.objects.all()})

        user_id = request.POST.get('user_id')
        user = get_object_or_404(CustomUser, id=user_id)

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

    users = CustomUser.objects.all()
    return render(request, 'mohi/issue_loan.html', {'users': users})

@login_required
def loan_list(request):
    if request.user.is_staff:
        loans = Loan.objects.all()
    else:
        loans = Loan.objects.filter(user=request.user)
    return render(request, 'mohi/loan_list.html', {'loans': loans})

@login_required
def loan_detail(request, loan_id):
    loan = get_object_or_404(Loan, id=loan_id)
    if not request.user.is_staff and loan.user != request.user:
        return redirect('loan_list')
    schedule = loan.generate_amortization_schedule()
    repayments = Repayment.objects.filter(loan=loan)
    return render(request, 'mohi/loan_detail.html', {'loan': loan, 'schedule': schedule, 'repayments': repayments})

@login_required
def make_repayment(request, loan_id):
    loan = get_object_or_404(Loan, id=loan_id)
    if not request.user.is_staff and loan.user != request.user:
        return redirect('loan_list')
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
    loans = Loan.objects.all()
    return render(request, 'mohi/loan_report.html', {'total_loans': total_loans, 'total_repayments': total_repayments, 'loans': loans})
def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('username')
        password = request.POST.get('password')
        print(f"Attempting login for email: {email}")
        user = authenticate(request, username=email, password=password)
        print(f"Authenticate returned: {user}")
        if user is not None:
            print("Login successful")
            login(request, user)
            return redirect('home')
        else:
            print("Login failed")
            return render(request, 'mohi/login.html', {'error': 'Invalid email or password.'})
    return render(request, 'mohi/login.html')

def logout_view(request):
    logout(request)
    return redirect('/')


def calculate_loan(principal, monthly_rate, months):
    """
    Calculate loan details for a reducing balance loan.
    Args:
        principal (float): Loan amount
        monthly_rate (float): Monthly interest rate in percent (e.g., 1 for 1%)
        months (int): Loan term in months
    Returns:
        dict: Monthly payment, total interest, total paid, and amortization schedule
    """
    # Input validation
    if principal <= 0 or monthly_rate < 0 or months <= 0:
        raise ValueError("Principal and months must be positive, and monthly rate must be non-negative.")

    # Convert monthly rate to decimal
    r = monthly_rate / 100  # e.g., 1% = 0.01
    
    # Calculate monthly payment using the formula: M = P * [r(1+r)^n / ((1+r)^n - 1)]
    if r == 0:  # Handle zero interest case
        monthly_payment = principal / months
    else:
        monthly_payment = principal * (r * (1 + r) ** months) / ((1 + r) ** months - 1)
    
    # Initialize amortization schedule
    balance = principal
    total_interest = 0
    schedule = []
    
    # Generate amortization schedule
    for month in range(1, months + 1):
        # Calculate interest for the current month
        interest = balance * r
        # Calculate principal portion of payment
        principal_paid = monthly_payment - interest
        # Update balance
        balance -= principal_paid
        
        # Ensure balance doesn't go negative
        if balance < 0:
            principal_paid += balance  # Adjust principal to avoid negative balance
            balance = 0
        
        total_interest += interest
        
        # Store schedule details
        schedule.append({
            'month': month,
            'payment': round(monthly_payment, 2),
            'interest': round(interest, 2),
            'principal': round(principal_paid, 2),
            'balance': round(balance, 2)
        })
        
        # Break if balance is paid off
        if balance <= 0:
            break
    
    # Adjust final payment if there's a small remaining balance
    if balance > 0:
        final_payment = balance + (balance * r)
        total_interest += balance * r
        schedule.append({
            'month': len(schedule) + 1,
            'payment': round(final_payment, 2),
            'interest': round(balance * r, 2),
            'principal': round(balance, 2),
            'balance': 0.00
        })
    
    # Calculate total paid
    total_paid = sum(item['payment'] for item in schedule)
    
    return {
        'monthly_payment': round(monthly_payment, 2),
        'total_interest': round(total_interest, 2),
        'total_paid': round(total_paid, 2),
        'schedule': schedule
    }

def loan_calculator(request):
    if request.method == 'POST':
        try:
            principal = float(request.POST.get('loanAmount'))
            months = int(request.POST.get('loanTerm'))
            monthly_rate = 1.0  # Fixed 1% monthly interest rate
            loan_details = calculate_loan(principal, monthly_rate, months)
            timestamp = timezone.now()
            # Redirect with query parameters instead of keyword arguments
            query_params = f"?principal={principal}&months={months}&monthly_payment={loan_details['monthly_payment']}&total_interest={loan_details['total_interest']}&total_paid={loan_details['total_paid']}&schedule={str(loan_details['schedule']).replace(' ', '')}&timestamp={timestamp.isoformat()}"
            return redirect(f"/pdf_preview/{query_params}")
        except ValueError as e:
            return render(request, 'mohi/loan_calculator.html', {'error': str(e)})
    return render(request, 'mohi/loan_calculator.html')



from datetime import timedelta
import datetime

def pdf_preview(request):
    try:
        principal = float(request.GET.get('principal'))
        months = int(request.GET.get('months'))
        monthly_payment = float(request.GET.get('monthly_payment'))
        total_interest = float(request.GET.get('total_interest'))
        total_paid = float(request.GET.get('total_paid'))
        schedule_data = eval(request.GET.get('schedule'))
        timestamp_str = request.GET.get('timestamp')
        
        # Convert timestamp to date only, fixing ISO format
        if ' ' in timestamp_str:
            timestamp_str = timestamp_str.replace(' ', '+')
        base_date = dt.fromisoformat(timestamp_str).date()
        
        # Generate payment dates using timedelta (approximate)
        schedule_with_dates = []
        for i, item in enumerate(schedule_data, 1):
            new_item = item.copy()
            new_item['date'] = base_date + timedelta(days=30 * (i - 1))
            schedule_with_dates.append(new_item)
        
        context = {
            'principal': principal,
            'months': months,
            'monthly_payment': monthly_payment,
            'total_interest': total_interest,
            'total_paid': total_paid,
            'schedule': schedule_with_dates,
            'timestamp': base_date
        }
        return render(request, 'mohi/pdf_preview.html', context)
    except (ValueError, TypeError) as e:
        print(f"{e}")
      



@csrf_exempt
def generate_pdf(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        loan = data['loan']
        schedule = loan['schedule']
        repayments = data['repayments']

        # Generate LaTeX content
        latex_content = r"""
\documentclass[a4paper,12pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{geometry}
\geometry{margin=1in}
\usepackage{booktabs}
\usepackage{amsmath}
\usepackage{amsfonts}
\usepackage{times} % Reliable font package

% Begin document
\begin{document}

% Title and User Information
\begin{center}
    \textbf{Payment Schedule - Loan \#%d}
    \vspace{0.5cm}
\end{center}

% User Information
\section*{User Information}
\begin{itemize}
    \item Email: %s
    \item Name: %s
    \item Department: %s
    \item Designation: %s
\end{itemize}

% Loan Summary
\section*{Loan Summary}
\begin{itemize}
    \item Amount: KSH %.2f
    \item Term: %d months
    \item Start Date: %s
    \item Balance: KSH %.2f
    \item Status: %s
\end{itemize}

% Payment Schedule Table
\section*{Payment Schedule}
\begin{table}[h]
    \centering
    \begin{tabular}{cccccc}
        \toprule
        Month & Date & Payment (KSH) & Interest (KSH) & Principal (KSH) & Balance (KSH) \\
        \midrule
        """ % (
            loan['id'],
            loan['user']['email'],
            loan['user']['name'],
            loan['user']['department'],
            loan['user']['designation'],
            loan['amount'],
            loan['term_months'],
            loan['start_date'],
            loan['balance'],
            loan['status']
        )

        for item in schedule:
            latex_content += r"%d & %s & %.2f & %.2f & %.2f & %.2f \\" % (
                item['month'],
                item['date'],
                item['payment'],
                item['interest'],
                item['principal'],
                item['balance']
            )

        latex_content += r"""
        \bottomrule
    \end{tabular}
\end{table}

% Repayments Table
\section*{Repayments}
\begin{table}[h]
    \centering
    \begin{tabular}{cccc}
        \toprule
        Date & Amount (KSH) & Principal (KSH) & Interest (KSH) \\
        \midrule
        """

        for repayment in repayments:
            latex_content += r"%s & %.2f & %.2f & %.2f \\" % (
                repayment.date,
                repayment.amount * 130,
                repayment.principal * 130,
                repayment.interest * 130
            )

        latex_content += r"""
        \bottomrule
    \end{tabular}
\end{table}

\end{document}
"""

        # Write LaTeX to temporary file
        tex_file = os.path.join(settings.MEDIA_ROOT, 'temp_payment_schedule.tex')
        with open(tex_file, 'w') as f:
            f.write(latex_content)

        # Compile LaTeX to PDF
        pdf_file = os.path.join(settings.MEDIA_ROOT, 'temp_payment_schedule.pdf')
        subprocess.run(['latexmk', '-pdf', tex_file], cwd=settings.MEDIA_ROOT, check=True)

        # Return PDF as response
        with open(pdf_file, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename=Payment_Schedule_Loan_{loan["id"]}.pdf'
            return response

        # Clean up
        os.remove(tex_file)
        os.remove(pdf_file)
    return JsonResponse({'error': 'Invalid request'}, status=400)