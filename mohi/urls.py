from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('apply_loan/', views.apply_loan, name='apply_loan'),
    path('loans/', views.loan_list, name='loan_list'),
    path('loans/<int:loan_id>/', views.loan_detail, name='loan_detail'),
    path('loans/<int:loan_id>/repay/', views.make_repayment, name='make_repayment'),
    path('report/', views.loan_report, name='loan_report'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
]