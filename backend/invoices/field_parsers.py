import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class InvoiceFieldParser:
    """
    A utility class to parse specific invoice fields from raw OCR text
    using multiple regex patterns to cover common variations.
    """

    def __init__(self, ocr_data, ocr_json=None):
        """
        ocr_data:        full_text_annotation.text from Vision AI
        ocr_json:        optional Vision AI response object (so we can grab tables if available)
        """
        self.ocr_text = ocr_data.get('text', '').upper()
        self.ocr_json = ocr_json
        self.lines = self.ocr_text.split('\n')
        self.extracted_fields = {}
        logger.info(f"Initialized InvoiceFieldParser with OCR Text (first 500 chars): {self.ocr_text[:500]}")
        logger.info(f"OCR JSON presence: {'Yes' if self.ocr_json else 'No'}")

    def parse_field(self, regex_patterns):
        if not self.ocr_text:
            return None
        for pattern in regex_patterns:
            match = re.search(pattern, self.ocr_text, re.IGNORECASE | re.MULTILINE)
            if match:
                logger.debug(f"Matched pattern '{pattern}' with value '{match.group(1).strip()}'")
                return match.group(1).strip()
        logger.debug(f"No match found for patterns: {regex_patterns}")
        return None

    def parse_invoice_number(self):
        patterns = [
            r"INVOICE(?:\s*NO\.?|\s*NUMBER)?\s*[:#]?\s*([A-Z0-9\-/]+)",
            r"INV(?:\s*NO)?\.?\s*[:#]?\s*([A-Z0-9\-/]+)",
            r"BILL\s*NO\.?\s*[:#]?\s*([A-Z0-9\-/]+)",
            r"TAX\s*INVOICE\s*[:#]?\s*([A-Z0-9\-/]+)",
        ]
        return self._find_first_match(patterns, "invoice_number")

    def parse_invoice_date(self):
        patterns = [
            r"DATE\s*[:.]?\s*(\d{1,2}[/\.-]\d{1,2}[/\.-]\d{2,4})",
            r"INVOICE\s*DATE\s*[:.]?\s*(\d{1,2}[/\.-]\d{1,2}[/\.-]\d{2,4})",
            r"BILL\s*DATE\s*[:.]?\s*(\d{1,2}[/\.-]\d{1,2}[/\.-]\d{2,4})",
            r"(\d{1,2}[/\.-]\d{1,2}[/\.-]\d{2,4})" # General date pattern
        ]
        date_str = self._find_first_match(patterns)
        if date_str:
            try:
                # Try parsing with common formats
                for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%d.%m.%y"]:
                    try:
                        return datetime.strptime(date_str, fmt).date()
                    except ValueError:
                        continue
                logger.warning(f"Could not parse date format: {date_str}")
                return None
            except Exception as e:
                logger.error(f"Error parsing invoice date {date_str}: {e}")
                return None
        return None

    def parse_seller_gstin(self):
        patterns = [
            r"SELLER\s*GSTIN\s*[:.]?\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})",
            r"GSTIN\s*[:.]?\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})",
            r"GST\s*NO\.?\s*[:.]?\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})",
            r"GST\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})",
        ]
        return self._find_first_match(patterns, "seller_gstin")

    def parse_buyer_name(self):
        # Prioritize finding "BILL TO", "CONSIGNEE", "CUSTOMER NAME" followed by a name
        patterns = [
            r"(?:BILL\s*TO|CONSIGNEE|CUSTOMER\s*NAME)\s*[:-]?\s*([A-Z0-9\s&\.,-]+)",
            r"BUYER\s*NAME\s*[:-]?\s*([A-Z0-9\s&\.,-]+)",
            r"TO\s*[:]?\s*([A-Z0-9\s&\.,-]+)",
        ]
        
        # Try to find buyer name based on common patterns
        buyer_name = self._find_first_match(patterns)
        if buyer_name:
            # Further refinement: remove state/code if captured
            buyer_name = re.sub(r',?\s*(?:[A-Z][a-z]+,\s*CODE:\s*\d{2})', '', buyer_name).strip()
            return buyer_name
        
        # Fallback: if 'BILL TO' etc. not found, try to locate names near GSTIN
        # This is a more complex heuristic and might require positional analysis from ocr_json
        if self.ocr_json:
            for page in self.ocr_json.get('pages', []):
                for block in page.get('blocks', []):
                    for paragraph in block.get('paragraphs', []):
                        para_text = ''.join([symbol.get('text', '') for word in paragraph.get('words', []) for symbol in word.get('symbols', [])])
                        if re.search(r'[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}', para_text):
                            # Found a GSTIN. Look for text above or near it
                            # This needs more sophisticated positional logic,
                            # for now, let's just avoid state codes if found.
                            # More advanced logic would involve bounding boxes from ocr_json
                            pass # Placeholder for future OCR_JSON based positional parsing

        # If none of the above, try a general name pattern (less reliable)
        general_name_patterns = [
            r"ATTN:\s*([A-Z0-9\s&\.,-]+)",
            r"M/S\.?\s*([A-Z0-9\s&\.,-]+)"
        ]
        buyer_name = self._find_first_match(general_name_patterns)
        if buyer_name:
            buyer_name = re.sub(r',?\s*(?:[A-Z][a-z]+,\s*CODE:\s*\d{2})', '', buyer_name).strip()
            return buyer_name
        
        return None

    def parse_buyer_gstin(self):
        patterns = [
            r"BUYER\s*GSTIN\s*[:.]?\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})",
            r"BILL\s*TO\s*GSTIN\s*[:.]?\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})",
            r"SHIP\s*TO\s*GSTIN\s*[:.]?\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})",
            r"GSTIN\s*OF\s*RECIPIENT\s*[:.]?\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})",
            r"RECIPIENT\s*GSTIN\s*[:.]?\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})",
            # General GSTIN pattern, excluding the seller's GSTIN if already found
            r"(?<!SELLER\s*GSTIN\s*[:.]?)\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})"
        ]
        gstin_matches = []
        for line in self.lines:
            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    gstin = match.group(1)
                    if gstin not in gstin_matches and gstin != self.extracted_fields.get("seller_gstin"):
                        gstin_matches.append(gstin)
        return gstin_matches[0] if gstin_matches else None

    def parse_total_tax_amount(self):
        patterns = [
            r"(?:TOTAL\s*TAX|TAX\s*AMOUNT|GST\s*AMOUNT)\s*[:.]?\s*(?:RS\.?|INR)?\s*([0-9]+\.[0-9]{2})",
            r"TAX\s*TOTAL\s*[:.]?\s*(?:RS\.?|INR)?\s*([0-9]+\.[0-9]{2})",
            r"TOTAL\s*GST\s*[:.]?\s*(?:RS\.?|INR)?\s*([0-9]+\.[0-9]{2})",
            r"SGST\s*\+\s*CGST\s*[:.]?\s*(?:RS\.?|INR)?\s*([0-9]+\.[0-9]{2})",
            r"IGST\s*[:.]?\s*(?:RS\.?|INR)?\s*([0-9]+\.[0-9]{2})"
        ]
        amount = self._find_first_match(patterns)
        return float(amount) if amount else None

    def parse_grand_total(self):
        patterns = [
            r"(?:GRAND\s*TOTAL|NET\s*AMOUNT|TOTAL\s*AMOUNT|AMOUNT\s*PAYABLE|TOTAL)\s*[:.]?\s*(?:RS\.?|INR)?\s*([0-9]+(?:,[0-9]{3})*\.[0-9]{2})",
            r"TOTAL\s*VALUE\s*[:.]?\s*(?:RS\.?|INR)?\s*([0-9]+(?:,[0-9]{3})*\.[0-9]{2})",
            r"AMOUNT\s*IN\s*FIGURES\s*[:.]?\s*(?:RS\.?|INR)?\s*([0-9]+(?:,[0-9]{3})*\.[0-9]{2})",
            r"BALANCE\s*DUE\s*[:.]?\s*(?:RS\.?|INR)?\s*([0-9]+(?:,[0-9]{3})*\.[0-9]{2})",
            r"TOTAL\s*(?:RS\.?|INR)?\s*([0-9]+(?:,[0-9]{3})*\.[0-9]{2})"
        ]
        
        # Prioritize patterns with 'RS.' or 'INR' or rupee symbol
        rupee_symbol_patterns = [
            r"₹\s*([0-9]+(?:,[0-9]{3})*\.[0-9]{2})",
            r"(?:RS\.?|INR)\s*([0-9]+(?:,[0-9]{3})*\.[0-9]{2})",
            r"(?:GRAND\s*TOTAL|NET\s*AMOUNT|TOTAL\s*AMOUNT|AMOUNT\s*PAYABLE|TOTAL)\s*[:.]?\s*₹\s*([0-9]+(?:,[0-9]{3})*\.[0-9]{2})"
        ]
        
        for pattern in rupee_symbol_patterns:
            for line in self.lines:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    amount_str = match.group(1).replace(',', '')
                    return float(amount_str)
        
        # Fallback to general patterns if rupee symbol/explicit currency not found
        amount = self._find_first_match(patterns)
        return float(amount.replace(',', '')) if amount else None

    def parse_line_items(self):
        line_items = []
        if self.ocr_json and self.ocr_json.get('pages') and self.ocr_json['pages'][0].get('tables'):
            logger.info("Attempting to parse line items from ocr_json tables.")
            # Assume the first table on the first page contains line items
            for table in self.ocr_json['pages'][0]['tables']:
                for row in table.get('rows', []):
                    item_data = {}
                    cells = row.get('cells', [])
                    
                    # Basic assumption: map cell index to field. This needs to be robustified
                    # by mapping column headers to content.
                    # For demonstration, let's assume a fixed order based on common invoice structure.
                    
                    # Example of extracting cell text
                    # You would need more sophisticated logic to map cells to specific fields
                    # like 'description', 'quantity', 'rate', 'taxable_value', 'total'
                    
                    # This is a simplistic mapping; a real solution would involve header detection
                    # or more advanced positional analysis using bounding boxes.
                    
                    # Let's try to extract text from cells and assign them to known keys
                    # This is a very rough example and will need significant refinement based on actual invoice layouts.
                    
                    # It's better to implement a logic that identifies columns based on content
                    # or headers, rather than assuming fixed indices.
                    
                    # For now, a very basic attempt to get some values.
                    # This section needs to be heavily customized based on the actual table structure.
                    
                    # Example: if first cell is description, second quantity, etc.
                    # This is a simplified approach, a more robust solution would involve
                    # analyzing the table headers or using semantic understanding.
                    if len(cells) > 0:
                        item_data['description'] = self._get_cell_text(cells[0])
                    if len(cells) > 1:
                        item_data['quantity'] = self._try_float(self._get_cell_text(cells[1]))
                    if len(cells) > 2:
                        item_data['rate'] = self._try_float(self._get_cell_text(cells[2]))
                    if len(cells) > 3:
                        item_data['taxable_value'] = self._try_float(self._get_cell_text(cells[3]))
                    if len(cells) > 4:
                        item_data['total'] = self._try_float(self._get_cell_text(cells[4]))
                    
                    if item_data.get('description'): # Only add if description is present
                        line_items.append(item_data)
            
            if line_items:
                logger.info(f"Successfully parsed {len(line_items)} line items from ocr_json tables.")
                return line_items
        
        logger.info("Falling back to regex-based line item parsing (no ocr_json tables or parsing failed).")
        # Fallback to regex-based parsing if ocr_json tables are not available or parsing from them fails
        # This regex attempts to capture common line item patterns
        # Adjust patterns to be more flexible and capture all relevant fields
        line_item_pattern = re.compile(
            r"(\d+)\s+" # Item number (group 1)
            r"(.+?)\s+" # Description (group 2, non-greedy)
            r"([A-Z0-9]{4,8})?\s*" # HSN/SAC (optional, group 3)
            r"(\d+\.?\d*)\s+" # Quantity (group 4)
            r"(\d+\.?\d*)\s+" # Rate (group 5)
            r"(\d+\.?\d*)\s+" # Taxable Value (group 6)
            r"(\d+\.?\d*)?" # Tax Percentage (optional, group 7)
            r"(\d+\.?\d*)" # Total (group 8)
        )

        for line in self.lines:
            match = line_item_pattern.search(line)
            if match:
                try:
                    line_items.append({
                        "description": match.group(2).strip(),
                        "hsn_sac": match.group(3).strip() if match.group(3) else None,
                        "quantity": float(match.group(4)),
                        "rate": float(match.group(5)),
                        "taxable_value": float(match.group(6)),
                        "tax_percentage": float(match.group(7)) if match.group(7) else None,
                        "total": float(match.group(8))
                    })
                except Exception as e:
                    logger.warning(f"Error parsing line item from line '{line}': {e}")
        
        logger.info(f"Parsed {len(line_items)} line items using regex fallback.")
        return line_items

    def _get_cell_text(self, cell):
        """Helper to extract text from a Vision API table cell."""
        text_segments = []
        for block in cell.get('blocks', []):
            for paragraph in block.get('paragraphs', []):
                for word in paragraph.get('words', []):
                    text_segments.append(''.join([s.get('text', '') for s in word.get('symbols', [])]))
        return ' '.join(text_segments).strip()

    def _try_float(self, value_str):
        """Helper to convert string to float, handling potential errors."""
        try:
            return float(value_str)
        except (ValueError, TypeError):
            return 0.0 # Default to 0.0 or handle as needed
            
    def _find_first_match(self, patterns, field_name=None):
        for line in self.lines:
            for pattern in patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    if field_name:
                        logger.info(f"Found {field_name}: {match.group(1)}")
                    return match.group(1).strip()
        if field_name:
            logger.info(f"Could not find {field_name}.")
        return None
