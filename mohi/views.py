from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import timedelta
from .decorators import is_staff_required
from .models import CustomUser, Loan, Repayment
from django.db.models.functions import TruncMonth
import logging
import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
import subprocess
import os
from django.conf import settings
from django.core.paginator import Paginator
from decimal import Decimal, InvalidOperation
from django.contrib import messages


# from datetime import date as dt

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)



def home(request):
    context = {}
    if request.user.is_authenticated:
        exchange_rate = 1  # 1 USD = 1 KSH
        if request.user.is_staff:
            loans = Loan.objects.all()
            total_loans = loans.count()
            total_amount = loans.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            total_paid = Repayment.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            context.update({
                'total_loans': total_loans,
                'total_amount': total_amount * exchange_rate,
                'total_paid': total_paid * exchange_rate
            })
        else:
            user_loans = Loan.objects.filter(user=request.user)
            context['user_loans'] = user_loans
            if user_loans.exists():
                user_total_amount = user_loans.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                user_total_paid = Repayment.objects.filter(loan__in=user_loans).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                context.update({
                    'user_total_amount': user_total_amount * exchange_rate,
                    'user_total_paid': user_total_paid * exchange_rate
                })
    return render(request, 'mohi/home.html', context)

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

        messages.success(request, "User registered successfully.")
        return render(request, 'mohi/register.html', {'show_success': True})

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
    search_query = request.GET.get('search', '')
    loans = Loan.objects.all() if request.user.is_staff else Loan.objects.filter(user=request.user)
    if search_query:
        loans = loans.filter(
            Q(id__icontains=search_query.strip()) |
            Q(user__email__icontains=search_query.strip()) |
            Q(is_paid__icontains=search_query.strip())
        )
    # Update balance for each loan based on repayments
    for loan in loans:
        total_repaid = Repayment.objects.filter(loan=loan).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        loan.balance = max(Decimal('0.00'), loan.amount - total_repaid)
        if loan.balance <= Decimal('0.00'):
            loan.is_paid = True
        else:
            loan.is_paid = False
        loan.save()

    # Pagination
    paginator = Paginator(loans, 10)  # 10 loans per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    # Stats
    total_loans = loans.count()
    total_amount = loans.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_paid = Repayment.objects.filter(loan__in=loans).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    exchange_rate = 1  # 1 USD = 1 KSH
    total_amount_ksh = total_amount * exchange_rate
    total_paid_ksh = total_paid * exchange_rate
    return render(request, 'mohi/loan_list.html', {
        'loans': page_obj,
        'total_loans': total_loans,
        'total_amount': total_amount_ksh,
        'total_paid': total_paid_ksh,
        'search_query': search_query,
        'is_paginated': True,
        'page_obj': page_obj
    })



@login_required
def loan_detail(request, loan_id):
    loan = get_object_or_404(Loan, id=loan_id)
    if not request.user.is_staff and loan.user != request.user:
        return redirect('loan_list')
    
    # Generate the original amortization schedule
    schedule = loan.generate_amortization_schedule(original=True)
    repayments = Repayment.objects.filter(loan=loan)
    exchange_rate = Decimal('1')  # 1 USD = 1 KSH
    
    # Calculate current balance based on principal repaid
    total_principal_repaid = sum(rep.principal for rep in repayments) or Decimal('0.00')
    loan_ksh_amount = loan.amount * exchange_rate
    loan_ksh_balance = max(Decimal('0.00'), loan.amount - total_principal_repaid) * exchange_rate
    
    # Update loan status
    loan.balance = loan_ksh_balance
    loan.is_paid = loan_ksh_balance <= Decimal('0.00')
    if loan.is_paid and not loan.end_date:
        loan.end_date = timezone.now().date()
    loan.save()
    
    # Convert schedule and repayments to KSH
    schedule_ksh = [
        {
            'month': item['month'],
            'date': item['date'],
            'payment': item['payment'] * float(exchange_rate),
            'interest': item['interest'] * float(exchange_rate),
            'principal': item['principal'] * float(exchange_rate),
            'balance': item['balance'] * float(exchange_rate)
        } for item in schedule
    ]
    repayments_ksh = [
        {
            'date': rep.date,
            'amount': float(rep.amount * exchange_rate),
            'principal': float(rep.principal * exchange_rate),
            'interest': float(rep.interest * exchange_rate)
        } for rep in repayments
    ]
    
    # Calculate total paid, keeping Decimal until final conversion
    total_paid = sum(rep.amount for rep in repayments) or Decimal('0.00')
    total_paid_ksh = float(total_paid * exchange_rate)
    
    return render(request, 'mohi/loan_detail.html', {
        'loan': loan,
        'schedule': schedule_ksh,
        'repayments': repayments_ksh,
        'loan_ksh_amount': float(loan_ksh_amount),
        'loan_ksh_balance': float(loan_ksh_balance),
        'monthly_payment': schedule[0]['payment'] * float(exchange_rate) if schedule else 0.0,
        'total_interest': sum(item['interest'] for item in schedule) * float(exchange_rate),
        'total_paid': total_paid_ksh
    })



@login_required
def make_repayment(request, loan_id):
    loan = get_object_or_404(Loan, id=loan_id)
    if not request.user.is_staff and loan.user != request.user:
        return redirect('loan_list')
    
    # Generate adjusted schedule (accounts for repayments)
    schedule = loan.generate_amortization_schedule(original=False)
    repayments = Repayment.objects.filter(loan=loan)
    exchange_rate = Decimal('1')  # 1 USD = 1 KSH
    
    schedule_ksh = [
        {
            'month': item['month'],
            'date': item['date'],
            'payment': item['payment'] * float(exchange_rate),
            'interest': item['interest'] * float(exchange_rate),
            'principal': item['principal'] * float(exchange_rate),
            'balance': item['balance'] * float(exchange_rate)
        } for item in schedule
    ]
    repayments_ksh = [
        {
            'date': rep.date,
            'amount': float(rep.amount) * float(exchange_rate),
            'principal': float(rep.principal) * float(exchange_rate),
            'interest': float(rep.interest) * float(exchange_rate)
        } for rep in repayments
    ]
    
    if request.method == 'POST':
        with transaction.atomic():
            for i, item in enumerate(schedule_ksh):
                checkbox_name = f'paid_{i}'
                if request.POST.get(checkbox_name):
                    payment_amount = Decimal(str(item['payment']))
                    interest = Decimal(str(item['interest']))
                    principal = Decimal(str(item['principal']))
                    
                    # Create or update repayment
                    existing_repayment = repayments.filter(date=item['date']).first()
                    if existing_repayment:
                        existing_repayment.amount = payment_amount / exchange_rate
                        existing_repayment.principal = principal / exchange_rate
                        existing_repayment.interest = interest / exchange_rate
                        existing_repayment.save()
                    else:
                        Repayment.objects.create(
                            loan=loan,
                            date=item['date'],
                            amount=payment_amount / exchange_rate,
                            principal=principal / exchange_rate,
                            interest=interest / exchange_rate
                        )
                    # Update balance based on principal only
                    loan.balance -= principal / exchange_rate
            
            # Update loan status
            if loan.balance <= Decimal('0.00'):
                loan.balance = Decimal('0.00')
                loan.is_paid = True
                loan.end_date = timezone.now().date()
            loan.save()
        
        messages.success(request, "Loan repayments updated successfully.")
        return render(request, 'mohi/make_repayment.html', {
            'loan': loan,
            'schedule': schedule_ksh,
            'repayments': repayments_ksh,
            'show_success': True
        })
    
    return render(request, 'mohi/make_repayment.html', {
        'loan': loan,
        'schedule': schedule_ksh,
        'repayments': repayments_ksh,
        'show_success': False
    })

@login_required
def loan_download(request, loan_id):
    loan = get_object_or_404(Loan, id=loan_id)
    if not request.user.is_staff and loan.user != request.user:
        return redirect('loan_list')
    
    # Generate the original amortization schedule
    schedule = loan.generate_amortization_schedule(original=True)
    repayments = Repayment.objects.filter(loan=loan)
    exchange_rate = Decimal('1')  # 1 USD = 1 KSH
    
    # Convert schedule and repayments to KSH
    schedule_ksh = [
        {
            'month': item['month'],
            'date': item['date'],
            'payment': item['payment'] * float(exchange_rate),
            'interest': item['interest'] * float(exchange_rate),
            'principal': item['principal'] * float(exchange_rate),
            'balance': item['balance'] * float(exchange_rate)
        } for item in schedule
    ]
    repayments_ksh = [
        {
            'date': rep.date,
            'amount': float(rep.amount) * float(exchange_rate),
            'principal': float(rep.principal) * float(exchange_rate),
            'interest': float(rep.interest) * float(exchange_rate)
        } for rep in repayments
    ]
    
    return render(request, 'mohi/loan_download.html', {
        'loan': loan,
        'user': loan.user,
        'schedule': schedule_ksh,
        'repayments': repayments_ksh,
        'loan_ksh_amount': float(loan.amount * exchange_rate),
        'monthly_payment': schedule[0]['payment'] * float(exchange_rate) if schedule else 0.0,
        'total_interest': sum(item['interest'] for item in schedule) * float(exchange_rate),
        'total_paid': sum(rep.amount for rep in repayments) * float(exchange_rate) or 0.0
    })

@login_required
def loan_report(request):
    exchange_rate = 1
    chart_data = {}
    if request.user.is_staff:
        total_loans_count = Loan.objects.count()
        total_amount = Loan.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_repayments = Repayment.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        loans = Loan.objects.all()

        # Aggregate data for admin charts
        total_outstanding = max(Decimal('0.00'), total_amount - total_repayments)
        chart_data['loan_summary'] = {
            'labels': ['Total Amount', 'Total Repayments', 'Total Outstanding'],
            'data': [float(total_amount * exchange_rate), float(total_repayments * exchange_rate), float(total_outstanding * exchange_rate)],
            'backgroundColor': ['#1E3A8A', '#10B981', '#F59E0B']
        }
        repayments_by_month = Repayment.objects.annotate(month=TruncMonth('date')).values('month').annotate(total=Sum('amount')).order_by('month')
        chart_data['repayment_trend'] = {
            'labels': [item['month'].strftime('%Y-%m') for item in repayments_by_month],
            'data': [float(item['total'] * exchange_rate) for item in repayments_by_month],
            'borderColor': '#1E3A8A',
            'fill': False
        }
    else:
        user_loans = Loan.objects.filter(user=request.user)
        total_loans_count = user_loans.count()
        total_amount = user_loans.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_repayments = Repayment.objects.filter(loan__in=user_loans).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        loans = user_loans
        total_outstanding = max(Decimal('0.00'), total_amount - total_repayments)
        chart_data['loan_summary'] = {
            'labels': ['Your Total Amount', 'Your Total Repayments', 'Your Total Outstanding'],
            'data': [float(total_amount * exchange_rate), float(total_repayments * exchange_rate), float(total_outstanding * exchange_rate)],
            'backgroundColor': ['#1E3A8A', '#10B981', '#F59E0B']
        }

    context = {
        'total_loans': total_loans_count,
        'total_amount': total_amount * exchange_rate,
        'total_repayments': total_repayments * exchange_rate,
        'loans': loans,
        'chart_data': chart_data
    }
    return render(request, 'mohi/loan_report.html', context)



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


from datetime import datetime, timedelta
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
        base_date = datetime.fromisoformat(timestamp_str).date()
        
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
                repayment.amount * 1,
                repayment.principal * 1,
                repayment.interest * 1
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