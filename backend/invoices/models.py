from django.db import models
from django.contrib.auth.models import User

# Define choices for Invoice status
INVOICE_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('processing', 'Processing'),
    ('parsed', 'Parsed'),
    ('failed', 'Failed'),
    ('reconciled', 'Reconciled'),
]

# Define choices for upload status
UPLOAD_STATUS_CHOICES = [
    ('uploaded', 'Uploaded'),
    ('processing_ocr', 'Processing OCR'),
    ('ocr_completed', 'OCR Completed'),
    ('parsing_data', 'Parsing Data'),
    ('data_parsed', 'Data Parsed'),
    ('reconciliation_pending', 'Reconciliation Pending'),
    ('reconciliation_complete', 'Reconciliation Complete'),
    ('reconciliation_failed', 'Reconciliation Failed'),
]

class Invoice(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invoices')
    file = models.FileField(upload_to='invoices/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, choices=INVOICE_STATUS_CHOICES, default='pending')
    upload_status = models.CharField(max_length=50, choices=UPLOAD_STATUS_CHOICES, default='uploaded')
    ocr_data = models.JSONField(null=True, blank=True)
    ocr_json = models.JSONField(null=True, blank=True)

    # Added fields for structured data
    invoice_number = models.CharField(max_length=255, null=True, blank=True)
    invoice_date = models.DateField(null=True, blank=True)
    seller_gstin = models.CharField(max_length=15, null=True, blank=True)
    buyer_name = models.CharField(max_length=255, null=True, blank=True)
    buyer_gstin = models.CharField(max_length=15, null=True, blank=True)
    total_tax = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"Invoice {self.id} - {self.invoice_number or 'N/A'}"

class LineItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='line_items')
    description = models.TextField()
    hsn_sac = models.CharField(max_length=20, null=True, blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    taxable_value = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"Line Item {self.id} for Invoice {self.invoice.id}: {self.description}"
