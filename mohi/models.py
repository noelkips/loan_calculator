from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
import math


class CustomUserManager(BaseUserManager):
    def create_user(self, email, first_name, last_name, department, designation, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)
        user = self.model(
            email=email,
            first_name=first_name,
            last_name=last_name,
            department=department,
            designation=designation,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, first_name, last_name, department, designation, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(
            email, first_name, last_name, department, designation, password, **extra_fields
        )

class CustomUser(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    department = models.CharField(max_length=100)
    designation = models.CharField(max_length=100)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'department', 'designation']

    objects = CustomUserManager()

    def __str__(self):
        return self.email




from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone

class Loan(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'))
    term_months = models.PositiveIntegerField(default=12)
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    is_paid = models.BooleanField(default=False)

    def generate_amortization_schedule(self, original=False):
        """
        Generate amortization schedule for the loan, matching calculate_loan logic.
        Args:
            original (bool): If True, generate based on original terms; if False, adjust for repayments.
        Returns:
            list: Amortization schedule with month, date, payment, interest, principal, balance.
        """
        principal = self.amount if original else self.balance
        monthly_rate = Decimal('1.0')  # Fixed 1% monthly interest rate to match calculate_loan
        months = self.term_months
        r = monthly_rate / Decimal('100')  # Convert to decimal (1% = 0.01)
        
        # Calculate monthly payment
        if r == 0:
            monthly_payment = principal / months
        else:
            monthly_payment = principal * (r * (1 + r) ** months) / ((1 + r) ** months - 1)
        
        balance = principal
        schedule = []
        start_date = self.start_date or timezone.now().date()
        
        # Adjust for repayments if not original
        if not original:
            repayments = Repayment.objects.filter(loan=self).order_by('date')
            repaid_principal = sum(rep.principal for rep in repayments) or Decimal('0.00')
            balance = max(Decimal('0.00'), principal - repaid_principal)
            # Skip months already paid
            paid_months = repayments.count()
        else:
            paid_months = 0
        
        # Generate schedule
        for month in range(1 + paid_months, months + 1):
            interest = balance * r
            principal_paid = monthly_payment - interest
            balance -= principal_paid
            
            if balance < 0:
                principal_paid += balance
                balance = 0
            
            schedule.append({
                'month': month,
                'date': start_date + timedelta(days=30 * (month - 1)),
                'payment': float(round(monthly_payment, 2)),
                'interest': float(round(interest, 2)),
                'principal': float(round(principal_paid, 2)),
                'balance': float(round(balance, 2))
            })
            
            if balance <= 0:
                break
        
        # Handle final payment
        if balance > 0:
            final_payment = balance + (balance * r)
            schedule.append({
                'month': len(schedule) + 1,
                'date': start_date + timedelta(days=30 * len(schedule)),
                'payment': float(round(final_payment, 2)),
                'interest': float(round(balance * r, 2)),
                'principal': float(round(balance, 2)),
                'balance': 0.0
            })
        
        return schedule

    def get_status_display(self):
        return "Paid" if self.is_paid else "Active"

    def __str__(self):
        return f"Loan #{self.id} for {self.user.email}"

class Repayment(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    principal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    interest = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"Repayment of {self.amount} on {self.date}"