import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from invoices.models import Invoice

def export_ocr_json(invoice_id):
    try:
        invoice = Invoice.objects.get(id=invoice_id)
        if invoice.ocr_json:
            # Define the path to save the JSON file
            json_output_dir = os.path.join(os.path.dirname(__file__), 'invoices', 'ml_layoutlm')
            os.makedirs(json_output_dir, exist_ok=True)
            output_filepath = os.path.join(json_output_dir, f"invoice_{invoice_id}_ocr_json.json")
            
            with open(output_filepath, 'w', encoding='utf-8') as f:
                json.dump(invoice.ocr_json, f, indent=4, ensure_ascii=False)
            print(f"Successfully exported ocr_json for Invoice {invoice_id} to {output_filepath}")
        else:
            print(f"Invoice {invoice_id} does not have ocr_json data.")
    except Invoice.DoesNotExist:
        print(f"Invoice with ID {invoice_id} not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    # Replace 69 with the actual ID of the invoice you want to export
    # The last invoice you uploaded was #69.
    export_ocr_json(69) 