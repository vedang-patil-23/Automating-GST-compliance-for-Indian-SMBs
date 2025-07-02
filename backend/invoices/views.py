from django.shortcuts import render
from rest_framework import generics, permissions
from .models import Invoice
from .serializers import InvoiceSerializer

# Create your views here.

class InvoiceUploadView(generics.CreateAPIView):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]

class InvoiceDetailView(generics.RetrieveAPIView):
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]

# New view for listing invoices
class InvoiceListView(generics.ListAPIView):
    queryset = Invoice.objects.all().order_by('-uploaded_at') # Order by upload time descending
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated]
