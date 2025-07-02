import os
import json
import logging
from django.core.management.base import BaseCommand
from invoices.models import Invoice # This import will work because manage.py sets up the environment

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Exports OCR JSON data for a given invoice ID to a file.'

    def add_arguments(self, parser):
        parser.add_argument('--invoice_id', type=int, default=69,
                            help='The ID of the invoice to export OCR JSON for. Defaults to 69.')

    def handle(self, *args, **options):
        invoice_id = options['invoice_id']

        # Create the ocr_json directory if it doesn't exist
        # Path relative to where manage.py is run, or absolute
        json_dir = os.path.join(
            os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'ml_layoutlm', 'ocr_json'))
        )
        os.makedirs(json_dir, exist_ok=True)

        try:
            invoice = Invoice.objects.get(id=invoice_id)
        except Invoice.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"Invoice #{invoice_id} not found in the database."))
            return

        if not invoice.ocr_json:
            self.stderr.write(self.style.WARNING(f"No OCR JSON data found for Invoice #{invoice_id}."))
            return

        # Export the OCR JSON data
        output_file = os.path.join(json_dir, f'invoice_{invoice_id}.json')
        with open(output_file, 'w') as f:
            json.dump(invoice.ocr_json, f, indent=2)

        self.stdout.write(self.style.SUCCESS(f"OCR JSON data exported to {output_file}")) 