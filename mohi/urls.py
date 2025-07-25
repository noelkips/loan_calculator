from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('home/', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('apply_loan/', views.apply_loan, name='apply_loan'),
    path('loans/', views.loan_list, name='loan_list'),
    path('loans/<int:loan_id>/', views.loan_detail, name='loan_detail'),
    path('loans/<int:loan_id>/repay/', views.make_repayment, name='make_repayment'),
    path('report/', views.loan_report, name='loan_report'),
    
    path('logout/', views.logout_view, name='logout'),
    path('loan_calculator/', views.loan_calculator, name='loan_calculator'),
    path('pdf_preview/', views.pdf_preview, name='pdf_preview'),
    
]