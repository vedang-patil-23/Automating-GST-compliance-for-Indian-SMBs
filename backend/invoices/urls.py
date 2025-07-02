from django.urls import path
from .views import InvoiceUploadView, InvoiceDetailView, InvoiceListView

urlpatterns = [
    path('upload/', InvoiceUploadView.as_view(), name='invoice-upload'),
    path('<int:pk>/', InvoiceDetailView.as_view(), name='invoice-detail'),
    path('', InvoiceListView.as_view(), name='invoice-list'),
] 