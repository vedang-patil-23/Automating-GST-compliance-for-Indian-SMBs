from rest_framework import serializers
from .models import Invoice
from .tasks import run_ocr_on_invoice

class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invoice
        fields = ['id', 'user', 'file', 'uploaded_at', 'ocr_data', 'status']
        read_only_fields = ['id', 'user', 'uploaded_at', 'ocr_data', 'status']

    def create(self, validated_data):
        user = self.context['request'].user
        invoice = Invoice.objects.create(user=user, **validated_data)
        run_ocr_on_invoice.delay(invoice.id)
        return invoice 