from celery import shared_task
from .models import Invoice
# from PIL import Image # No longer needed for Google Vision
# import pytesseract # No longer needed for Google Vision
from .parsers import parse_invoice_data
import os
import datetime
import json
import logging

# Import Google Cloud Vision libraries
from google.cloud import vision
from google.protobuf.json_format import MessageToDict
import io

# Import the InvoiceFieldParser
from .field_parsers import InvoiceFieldParser

logger = logging.getLogger(__name__)

@shared_task
def run_ocr_on_invoice(invoice_id):
    try:
        invoice = Invoice.objects.get(id=invoice_id)
        image_path = invoice.file.path
        
        logger.info(f"Attempting to OCR file at path: {image_path} using Google Cloud Vision")

        # Initialize Google Cloud Vision client
        client = vision.ImageAnnotatorClient()

        # Load image into memory
        with io.open(image_path, 'rb') as image_file:
            content = image_file.read()

        image = vision.Image(content=content)

        # Perform OCR using Google Cloud Vision
        response = client.document_text_detection(image=image)

        raw_ocr_text = ""
        # Convert the entire response object to a dictionary first
        response_dict = MessageToDict(response._pb)

        if response_dict.get('fullTextAnnotation'):
            raw_ocr_text = response_dict['fullTextAnnotation']['text']
        
        # Save raw OCR text to a debug log file (as previously implemented)
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ocr_debug_logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"invoice_{invoice_id}_ocr_result_{timestamp}.txt"
        log_filepath = os.path.join(log_dir, log_filename)
        
        with open(log_filepath, 'w', encoding='utf-8') as f:
            f.write(raw_ocr_text)
        logger.info(f"Raw OCR result saved to: {log_filepath}")

        invoice.ocr_data = {'text': raw_ocr_text}
        invoice.ocr_json = response_dict.get('fullTextAnnotation') # Store the fullTextAnnotation part
        invoice.status = 'ocr_complete'
        invoice.save()

        # Trigger the parsing task
        parse_invoice_data.delay(invoice.id)

    except Invoice.DoesNotExist:
        logger.error(f"Invoice with ID {invoice_id} not found.")
    except Exception as e:
        logger.error(f"Error performing OCR for invoice {invoice_id}: {e}", exc_info=True)
        if invoice:
            invoice.status = 'ocr_failed'
            invoice.save() 