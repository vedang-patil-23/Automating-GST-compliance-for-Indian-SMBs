import json
import os
import logging
from generate_labels import LabelGenerator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_label_generator():
    # Initialize the LabelGenerator with the directory containing OCR JSON files
    json_dir = os.path.join(os.path.dirname(__file__), 'ocr_json')
    generator = LabelGenerator(json_dir)
    
    # Process a sample invoice (you can change this to test different invoices)
    sample_file = 'invoice_69.json'  # Replace with your test invoice JSON file
    file_path = os.path.join(json_dir, sample_file)
    
    if not os.path.exists(file_path):
        logger.error(f"Test file not found: {file_path}")
        return
    
    # Process the invoice
    result = generator.process_invoice(file_path)
    
    # Print the results in a readable format
    logger.info("\n=== Label Generation Results ===\n")
    
    # The result is the manifest, which contains a 'regions' key
    if 'regions' in result:
        for region_data in result['regions']:
            region_name = region_data['class']
            region_text = " ".join(region_data['words'])
            region_box = region_data['box']

            logger.info(f"\n{region_name}:")
            logger.info(f"  Text: {region_text}")
            logger.info(f"  Box: {region_box}")
            logger.info("  ---")
    else:
        logger.warning("No 'regions' key found in the result dictionary.")

if __name__ == "__main__":
    test_label_generator() 