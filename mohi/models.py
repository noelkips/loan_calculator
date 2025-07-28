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
        schedule = []
        balance = self.amount if original else self.balance
        monthly_rate = self.interest_rate / 100 / 12
        monthly_payment = (self.amount * monthly_rate * (1 + monthly_rate) ** self.term_months) / ((1 + monthly_rate) ** self.term_months - 1)
        current_date = self.start_date
        remaining_balance = balance

        for month in range(1, self.term_months + 1):
            interest = remaining_balance * monthly_rate
            principal = min(monthly_payment - interest, remaining_balance)
            remaining_balance -= principal
            if original:
                remaining_balance = max(0, self.amount - (month - 1) * principal)  # Simulate original declining balance
            schedule.append({
                'month': month,
                'date': current_date,
                'payment': monthly_payment,
                'interest': interest,
                'principal': principal,
                'balance': remaining_balance
            })
            current_date += timedelta(days=30)  # Approximate 1 month
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