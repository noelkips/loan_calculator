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

def print_loan_details(loan_details):
    """Print loan details and amortization schedule in a formatted way."""
    print(f"Loan Details:")
    print(f"Monthly Payment: ${loan_details['monthly_payment']}")
    print(f"Total Interest Paid: ${loan_details['total_interest']}")
    print(f"Total Paid: ${loan_details['total_paid']}")
    print("\nAmortization Schedule:")
    print(f"{'Month':<6} {'Payment':<10} {'Interest':<10} {'Principal':<10} {'Balance':<10}")
    print("-" * 46)
    for item in loan_details['schedule']:
        print(f"{item['month']:<6} ${item['payment']:<9.2f} ${item['interest']:<9.2f} ${item['principal']:<9.2f} ${item['balance']:<9.2f}")

# Example usage for $1,000 loan, 1% monthly interest, 7 months
try:
    print("REPAYMENT IN 12 MONTHS")
    loan = calculate_loan(65000, 1, 21)
    print_loan_details(loan)
    
    
except ValueError as e:
    print(f"Error: {e}")