from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from datetime import timedelta

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
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='loans')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=1.0)  # 1% monthly
    term_months = models.PositiveIntegerField()
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2)
    is_paid = models.BooleanField(default=False)

    def __str__(self):
        return f"Loan for {self.user.email} - {self.amount}"

    def calculate_monthly_payment(self):
        P = Decimal(str(self.amount))
        r = Decimal(str(self.interest_rate)) / 100  # Monthly rate
        n = self.term_months
        if r == 0:
            return P / n
        return P * (r * (1 + r) ** n) / ((1 + r) ** n - 1)

    def generate_amortization_schedule(self):
        monthly_payment = self.calculate_monthly_payment()
        balance = Decimal(str(self.balance))  # Convert initial balance to Decimal
        r = Decimal(str(self.interest_rate)) / 100
        schedule = []
        current_date = self.start_date
        for month in range(1, self.term_months + 1):
            interest = balance * r
            principal_paid = monthly_payment - interest
            if balance - principal_paid < 0:
                principal_paid = balance
                balance = Decimal('0.00')
            else:
                balance -= principal_paid
            days = (current_date - self.start_date).days if month == 1 else ((current_date - schedule[-1]['date']).days)
            schedule.append({
                'month': month,
                'date': current_date,
                'days': days,
                'payment': float(monthly_payment.quantize(Decimal('0.01'))),
                'interest': float(interest.quantize(Decimal('0.01'))),
                'principal': float(principal_paid.quantize(Decimal('0.01'))),
                'balance': float(balance.quantize(Decimal('0.01')))
            })
            if balance <= 0:
                break
            current_date += timedelta(days=30)  # Approximate 30-day month
        return schedule

class Repayment(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE)
    date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    principal = models.DecimalField(max_digits=10, decimal_places=2)
    interest = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Repayment for {self.loan} on {self.date}"