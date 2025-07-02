from celery import shared_task
from .models import Invoice, LineItem
from .field_parsers import InvoiceFieldParser
import logging

logger = logging.getLogger(__name__)

@shared_task
def parse_invoice_data(invoice_id):
    """
    Parse the OCR text from an invoice and extract structured data.
    """
    invoice = None # Initialize invoice to None for proper error handling
    try:
        invoice = Invoice.objects.get(id=invoice_id)
        if not invoice.ocr_data or not invoice.ocr_data.get('text'):
            logger.warning(f"No OCR data or text found for invoice {invoice_id}. Setting status to parsing_failed.")
            # Ensure status is set even if no OCR data
            if invoice:
                invoice.status = 'parsing_failed'
                invoice.save()
            return False

        # Pass both ocr_data (for text) and ocr_json (for structured table data) to the parser
        parser = InvoiceFieldParser(invoice.ocr_data, invoice.ocr_json)

        # Extract all fields using the parser
        invoice.invoice_number = parser.parse_invoice_number()
        invoice.invoice_date = parser.parse_invoice_date()
        invoice.seller_gstin = parser.parse_seller_gstin()
        invoice.buyer_name = parser.parse_buyer_name()
        invoice.buyer_gstin = parser.parse_buyer_gstin()
        invoice.total_tax = parser.parse_total_tax_amount()
        invoice.grand_total = parser.parse_grand_total()

        # Save the invoice first to ensure we have an ID for the line items
        invoice.save()

        # Clear existing line items
        invoice.line_items.all().delete()

        # Extract and create line items
        line_items_data = parser.parse_line_items()
        for item_data in line_items_data:
            LineItem.objects.create(
                invoice=invoice,
                description=item_data.get('description', ''),
                hsn_sac=item_data.get('hsn_sac', ''),
                quantity=item_data.get('quantity', 0.0),
                rate=item_data.get('rate', 0.0),
                taxable_value=item_data.get('taxable_value', 0.0),
                total=item_data.get('total', 0.0),
                tax_percentage=item_data.get('tax_percentage'),
                tax_amount=item_data.get('tax_amount'),
            )

        # Update status
        invoice.status = 'parsing_complete'
        invoice.save()

        logger.info(f"Successfully parsed invoice {invoice_id}")
        return True

    except Invoice.DoesNotExist:
        logger.error(f"Invoice {invoice_id} not found")
        return False
    except Exception as e:
        logger.error(f"Error parsing invoice {invoice_id}: {str(e)}", exc_info=True)
        if invoice:
            invoice.status = 'parsing_failed'
            invoice.save()
        return False
