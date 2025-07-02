import json
import os
import re
import math
from typing import Dict, List, Tuple, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define region classes
REGION_CLASSES = [
    "SELLER_INFO",
    "BILL_TO",
    "SHIP_TO",
    "INVOICE_NO",
    "INVOICE_DATE",
    "LINE_ITEM_TABLE",
    "TOTAL_TAX",
    "GRAND_TOTAL"
]

class LabelGenerator:
    def __init__(self, json_dir: str):
        self.json_dir = json_dir
        # Define regex patterns for full regions (fallback)
        self.patterns = {
            'SELLER_INFO': r'(?i)([^\\n]+(?:Hardwares|Traders|Enterprises|Pvt\\.?\\s*Ltd\\.?)[^\\n]*)\\s*\\n{1,2}(?:[^\\n]*\\n){0,3}GSTIN\\s*/\\s*UIN\\s*:\\s*([A-Z0-9]{15})',
            'BILL_TO': r'(?i)Buyer\\s*\\(\\s*Bill\\s*to\\s*\\)(?:\\s*|\\n*):?(?:\\s*|\\n*)(.*?)(?:\\s*|\\n*)GSTIN\\s*/\\s*UIN\\s*:\\s*([A-Z0-9]{15})(?:\\s*|\\n*)?',
            'SHIP_TO': r'(?i)Consignee\\s*\\(\\s*Ship\\s*to\\s*\\)(?:\\s*|\\n*):?(?:\\s*|\\n*)(.*?)(?:\\s*|\\n*)GSTIN\\s*/\\s*UIN\\s*:\\s*([A-Z0-9]{15})(?:\\s*|\\n*)?',
            'INVOICE_NO': r'(?i)(?:Invoice\\s*No\\.?|Invoice\\s*#|Inv\\.?\\s*No\\.?|Bill\\s*No\\.?)\\s*([A-Z0-9/.-]{5,20})(?=\\s*(?:Delivery|Reference|Dated|Buyer|Consignee|\\n{2,}|$))', # More constrained and flexible invoice number
            'INVOICE_DATE': r'(?i)Dated(?:\\s|\\n)+(\\d{1,2}\\s*-\\s*[A-Za-z]+\\s*-\\s*\\d{2})',
            'TOTAL_TAX': r'(?i)Total(?:\\s|\\n)+Tax\\s*Amount(?:\\s|\\n)+([\\d,]+\\.\\d{2})',
            'GRAND_TOTAL': r'(?i)Amount\\s*Chargeable\\s*\\(\\s*in\\s*words\\s*\\)(?:\\s|\\n)+Indian\\s*Rupee\\s*([A-Za-z\\s]+)\\s*Only',
            'LINE_ITEM_TABLE': r'(?s)(?:SI\\s*No\\.|Description|HSN|SAC|Quantity|Rate|Amount|CGST|SGST|Total)(?:.*?)(?=\\nTotal\\s*Taxable Value|Total\\s*Tax\\s*Amount|Amount\\s*Chargeable|Grand\\s*Total|Declaration|E\\.\\s*&\\s*O\\.\\s*E)' # Enhanced end detection
        }

        # Define regex patterns for labels (for spatial matching)
        self.label_patterns = {
            'GSTIN_LABEL': r'(?i)GSTIN(?:/UIN)?',
            'INVOICE_NO_LABEL': r'(?i)Invoice\\s*No\\.?|Invoice',
            'DATE_LABEL': r'(?i)Dated|Date',
            'TOTAL_TAX_LABEL': r'(?i)Total\\s*Tax\\s*Amount|Total\\s*Tax',
            'GRAND_TOTAL_LABEL': r'(?i)Amount\\s*Chargeable\\s*\\(\\s*in\\s*words\\s*\\)|Grand\\s*Total|Total\\s*Amount',
            'LINE_ITEM_TABLE_HEADER_KEYWORDS': r'(?i)SI\\s*No\\.|Description|HSN|SAC|Quantity|Rate|Amount|CGST|SGST|Total'
        }
        # Define regex patterns for values (for spatial matching)
        self.value_patterns = {
            'GSTIN_VALUE': r'[0-9A-Z]{15}',
            'INVOICE_NO_VALUE': r'[A-Z0-9/.-]+', # Relaxed to allow . and -
            'DATE_VALUE': r'\\d{1,2}\\s*-\\s*[A-Za-z]+\\s*-\\s*\\d{2}',
            'AMOUNT_VALUE': r'[\\d,]+\\.\\d{2}',
            'WORDS_AMOUNT_VALUE': r'Indian\\s*Rupee\\s*([A-Za-z\\s]+)\\s*Only'
        }

    def box_center(self, box):
        # box = [x0,y0,x1,y1]
        return ((box[0]+box[2]) / 2, (box[1]+box[3]) / 2)

    def euclidean(self, a, b):
        return math.hypot(a[0]-b[0], a[1]-b[1])

    def get_word_boxes_single(self, word_data: Dict, page_width: int, page_height: int) -> List[int]:
        """Extract normalized bounding box for a single word."""
        verts = word_data["boundingBox"]["vertices"]
        x_coords = [v.get("x", 0) for v in verts]
        y_coords = [v.get("y", 0) for v in verts]
        
        x0 = int(min(x_coords) / page_width * 1000)
        y0 = int(min(y_coords) / page_height * 1000)
        x1 = int(max(x_coords) / page_width * 1000)
        y1 = int(max(y_coords) / page_height * 1000)
        
        return [x0, y0, x1, y1]

    def extract_text_from_ocr(self, ocr_json: Dict) -> Tuple[str, List[Dict]]:
        """Extract text from OCR JSON while preserving structure and getting character spans for words."""
        full_text_parts = []
        word_info_list = []
        current_char_pos = 0

        for page in ocr_json.get('pages', []):
            page_width = page.get("width", 1)
            page_height = page.get("height", 1)
            for block in page.get('blocks', []):
                for paragraph in block.get('paragraphs', []):
                    para_words_text = []
                    for word_data in paragraph.get('words', []):
                        word_text = ''.join(symbol.get('text', '') for symbol in word_data.get('symbols', []))
                        if word_text.strip():
                            word_info = {
                                'text': word_text,
                                'box': self.get_word_boxes_single(word_data, page_width, page_height),
                                'start_char_idx': current_char_pos,
                                'end_char_idx': current_char_pos + len(word_text)
                            }
                            word_info_list.append(word_info)
                            para_words_text.append(word_text)
                            current_char_pos += len(word_text) + 1  # +1 for space after word

                    if para_words_text:
                        full_text_parts.append(' '.join(para_words_text))
                        current_char_pos -= 1 # Remove the last space added if it's the end of a paragraph
                    full_text_parts.append('\\n')
                    current_char_pos += 1
                full_text_parts.append('\\n') # Double newline for block separation
                current_char_pos += 1
            full_text_parts.append('\\n') # Triple newline for page separation
            current_char_pos += 1

        full_text = ''.join(full_text_parts)

        # No re-alignment needed here, `start_char_idx` and `end_char_idx` are direct.
        # The .strip() for full_text will be handled by the user of the text if needed.

        return full_text, word_info_list

    def find_span_from_word_boxes(self, full_text: str, words_in_span: List[Dict]) -> Optional[Tuple[int, int]]:
        """Find the start and end character span in full_text for a list of words."""
        if not words_in_span:
            return None
        
        # Ensure words are sorted by their start_char_idx
        sorted_words = sorted(words_in_span, key=lambda w: w['start_char_idx'])
        
        start_index = sorted_words[0]['start_char_idx']
        end_index = sorted_words[-1]['end_char_idx']
        
        # Validate if the reconstructed text from these words matches the segment in full_text
        # This is a robustness check. Minor mismatches in whitespace might occur.
        # Reconstructed text by simply joining might not be identical to full_text segment due to newline handling.
        # For now, rely on start_char_idx and end_char_idx directly as they are aligned.

        # The original code for `find_span_from_word_boxes` was problematic.
        # The `word_char_spans` list from `extract_text_from_ocr` should be used directly.
        
        return (start_index, end_index)

    def match_label_to_value(self, words, label_regex, value_regex, max_dist=200):
        """Words: list of dicts: [{'text':..., 'box':[x0,y0,x1,y1]}, ...]
        label_regex: regex for the label word (e.g. r'GSTIN')
        value_regex: regex for the value token (e.g. r'[0-9A-Z]{15}')
        """
        labels = [w for w in words if re.fullmatch(label_regex, w['text'], re.IGNORECASE)]
        values = [w for w in words if re.fullmatch(value_regex, w['text'])]
        matches = {}
        for lab in labels:
            lc = self.box_center(lab['box'])
            # find the closest value
            best = min(values, key=lambda v: self.euclidean(lc, self.box_center(v['box'])), default=None)
            if best and self.euclidean(lc, self.box_center(best['box'])) < max_dist:
                matches[lab['text']] = best # Return the full word_info dict for the value
        return matches

    def find_matches(self, words_with_spans: List[Dict], full_text: str) -> Dict[str, List[Tuple[int, int]]]:
        """Find matches for each region using spatial proximity and regex fallback."""
        matches = {region: [] for region in REGION_CLASSES}

        # Create a mapping of character positions to word_info for precise lookup
        char_to_word_info = {}
        for word_info in words_with_spans:
            for i in range(word_info['start_char_idx'], word_info['end_char_idx']):
                char_to_word_info[i] = word_info

        # --- Spatial Matching for specific fields ---

        # INVOICE_NO
        # Using a more robust spatial approach for INVOICE_NO
        invoice_no_label_words = [w for w in words_with_spans if re.search(self.label_patterns['INVOICE_NO_LABEL'], w['text'], re.IGNORECASE)]
        invoice_no_value_words = [w for w in words_with_spans if re.search(self.value_patterns['INVOICE_NO_VALUE'], w['text'])]

        for label_word in invoice_no_label_words:
            lc = self.box_center(label_word['box'])
            best_value_word = min(
                invoice_no_value_words,
                key=lambda v: self.euclidean(lc, self.box_center(v['box'])),
                default=None
            )
            if best_value_word and self.euclidean(lc, self.box_center(best_value_word['box'])) < 150: # max_dist for invoice number
                # Combine label and value for the span
                combined_words = sorted([label_word, best_value_word], key=lambda w: w['start_char_idx'])
                span = self.find_span_from_word_boxes(full_text, combined_words)
                if span:
                    matches['INVOICE_NO'].append(span)
                break # Assuming one invoice number

        # INVOICE_DATE
        invoice_date_matches_spatial = self.match_label_to_value(words_with_spans, self.label_patterns['DATE_LABEL'], self.value_patterns['DATE_VALUE'])
        for label_text, value_word_info in invoice_date_matches_spatial.items():
            label_word_info = next((w for w in words_with_spans if w['text'] == label_text), None)
            if label_word_info:
                combined_words = sorted([label_word_info, value_word_info], key=lambda w: w['start_char_idx'])
                span = self.find_span_from_word_boxes(full_text, combined_words)
                if span:
                    matches['INVOICE_DATE'].append(span)
                break

        # TOTAL_TAX
        total_tax_matches_spatial = self.match_label_to_value(words_with_spans, self.label_patterns['TOTAL_TAX_LABEL'], self.value_patterns['AMOUNT_VALUE'])
        for label_text, value_word_info in total_tax_matches_spatial.items():
            label_word_info = next((w for w in words_with_spans if w['text'] == label_text), None)
            if label_word_info:
                combined_words = sorted([label_word_info, value_word_info], key=lambda w: w['start_char_idx'])
                span = self.find_span_from_word_boxes(full_text, combined_words)
                if span:
                    matches['TOTAL_TAX'].append(span)
                break
        
        # GRAND_TOTAL
        grand_total_matches_spatial = self.match_label_to_value(words_with_spans, self.label_patterns['GRAND_TOTAL_LABEL'], self.value_patterns['AMOUNT_VALUE'])
        for label_text, value_word_info in grand_total_matches_spatial.items():
            label_word_info = next((w for w in words_with_spans if w['text'] == label_text), None)
            if label_word_info:
                combined_words = sorted([label_word_info, value_word_info], key=lambda w: w['start_char_idx'])
                span = self.find_span_from_word_boxes(full_text, combined_words)
                if span:
                    matches['GRAND_TOTAL'].append(span)
                break

        # SELLER_INFO, BILL_TO, SHIP_TO - Enhanced Spatial matching for GSTINs and surrounding text
        gstin_labels = [w for w in words_with_spans if re.fullmatch(self.label_patterns['GSTIN_LABEL'], w['text'], re.IGNORECASE)]
        gstin_values = [w for w in words_with_spans if re.fullmatch(self.value_patterns['GSTIN_VALUE'], w['text'])]

        for label_word in gstin_labels:
            lc = self.box_center(label_word['box'])
            best_gstin_value_word = min(
                gstin_values,
                key=lambda v: self.euclidean(lc, self.box_center(v['box'])),
                default=None
            )

            if best_gstin_value_word and self.euclidean(lc, self.box_center(best_gstin_value_word['box'])) < 300: # Increased max_dist for GSTIN
                gstin_value_box = best_gstin_value_word['box']
                
                # Check for "Buyer" / "Consignee" / "Seller" in words vertically above and horizontally aligned
                relevant_header_words = []
                for w in words_with_spans:
                    # Check if word is roughly above the GSTIN value and within a reasonable horizontal range
                    if w['box'][3] < gstin_value_box[1] and \
                       abs(self.box_center(w['box'])[0] - self.box_center(gstin_value_box)[0]) < 150: # Increased horizontal range
                        
                        if re.search(r'(?i)Buyer|Bill\\s*to', w['text']) and not matches.get('BILL_TO'):
                            relevant_header_words.append({'type': 'BILL_TO', 'word': w})
                        elif re.search(r'(?i)Consignee|Ship\\s*to', w['text']) and not matches.get('SHIP_TO'):
                            relevant_header_words.append({'type': 'SHIP_TO', 'word': w})
                        elif re.search(r'(?i)Surabhi\\s*Hardwares|Seller|Our\\s*GSTIN', w['text']) or \
                             ('GSTIN' in label_word['text'] and w['box'][1] < label_word['box'][1]) and not matches.get('SELLER_INFO'): # Heuristic for seller info: nearby text before GSTIN label
                            relevant_header_words.append({'type': 'SELLER_INFO', 'word': w})

                # Sort header words by their vertical position to get the top-most
                relevant_header_words.sort(key=lambda x: x['word']['box'][1])

                for header_info in relevant_header_words:
                    header_type = header_info['type']
                    header_word = header_info['word']

                    # Define span from header word to GSTIN value word
                    combined_words_for_region = sorted([header_word, best_gstin_value_word], key=lambda w: w['start_char_idx'])
                    span = self.find_span_from_word_boxes(full_text, combined_words_for_region)
                    
                    if span:
                        if header_type == 'SELLER_INFO' and not matches.get('SELLER_INFO'):
                            matches['SELLER_INFO'].append(span)
                            # Also try to include the actual business name for SELLER_INFO
                            seller_name_match = re.search(r'(?i)([^\\n]+(?:Hardwares|Traders|Enterprises|Pvt\\.?\\s*Ltd\\.?)[^\\n]*)(?:\\s*\\n{1,2}(?:[^\\n]*\\n){0,3}GSTIN)', full_text[span[0]:])
                            if seller_name_match:
                                new_span = (span[0] + seller_name_match.start(1), span[0] + seller_name_match.end(1))
                                matches['SELLER_INFO'][-1] = new_span # Replace with more precise span
                            break
                        elif header_type == 'BILL_TO' and not matches.get('BILL_TO'):
                            matches['BILL_TO'].append(span)
                            # Try to expand to include name/address if not already captured
                            bill_to_name_match = re.search(r'(?i)(Buyer\\s*\\(\\s*Bill\\s*to\\s*\\)(?:\\s*|\\n*):?(?:\\s*|\\n*)(.*?))(?:\\s*|\\n*)GSTIN', full_text[span[0]:])
                            if bill_to_name_match:
                                new_span = (span[0] + bill_to_name_match.start(1), span[0] + bill_to_name_match.end(1))
                                matches['BILL_TO'][-1] = new_span
                            break
                        elif header_type == 'SHIP_TO' and not matches.get('SHIP_TO'):
                            matches['SHIP_TO'].append(span)
                            # Try to expand to include name/address if not already captured
                            ship_to_name_match = re.search(r'(?i)(Consignee\\s*\\(\\s*Ship\\s*to\\s*\\)(?:\\s*|\\n*):?(?:\\s*|\\n*)(.*?))(?:\\s*|\\n*)GSTIN', full_text[span[0]:])
                            if ship_to_name_match:
                                new_span = (span[0] + ship_to_name_match.start(1), span[0] + ship_to_name_match.end(1))
                                matches['SHIP_TO'][-1] = new_span
                            break

        # LINE_ITEM_TABLE detection with enhanced spatial analysis
        table_header_keywords = [w for w in words_with_spans if re.search(self.label_patterns['LINE_ITEM_TABLE_HEADER_KEYWORDS'], w['text'])]
        
        if table_header_keywords:
            table_header_keywords.sort(key=lambda w: w['box'][1])
            table_start = table_header_keywords[0]['start_char_idx']
            
            # Find the end of the table by looking for the start of the summary section
            summary_start_keywords_patterns = [
                r'(?i)Total\\s*Taxable\\s*Value',
                r'(?i)Total\\s*Tax\\s*Amount',
                r'(?i)Amount\\s*Chargeable\\s*\\(\\s*in\\s*words\\s*\\)',
                r'(?i)Grand\\s*Total',
                r'(?i)Declaration',
                r'(?i)E\\.\\s*&\\s*O\\.\\s*E' # Added another common end marker
            ]
            
            table_end = None
            min_summary_start_idx = float('inf')

            for keyword_pattern in summary_start_keywords_patterns:
                for match in re.finditer(keyword_pattern, full_text):
                    if match.start(0) > table_start:
                        min_summary_start_idx = min(min_summary_start_idx, match.start(0))
            
            if min_summary_start_idx != float('inf'):
                table_end = min_summary_start_idx
            
            if table_end:
                matches['LINE_ITEM_TABLE'].append((table_start, table_end))
            else:
                # Fallback to regex if spatial matching for end fails
                table_match = re.search(self.patterns['LINE_ITEM_TABLE'], full_text)
                if table_match:
                    matches['LINE_ITEM_TABLE'].append((table_match.start(0), table_match.end(0)))

        # Fallback to regex patterns for any unmatched regions
        for region in REGION_CLASSES:
            if not matches[region]:
                pattern = self.patterns.get(region)
                if pattern:
                    match = re.search(pattern, full_text)
                    if match:
                        matches[region].append((match.start(0), match.end(0)))

        return matches

    def align_spans_to_words(self, full_text: str, spans: Dict[str, List[Tuple[int, int]]], 
                           words_with_spans: List[Dict]) -> Dict[str, List[Dict]]:
        """Align regex spans to OCR words and their boxes using character indices."""
        region_words = {region: [] for region in REGION_CLASSES}
        
        # Create a mapping of character positions to word_info for precise lookup
        char_to_word_info = {}
        for word_info in words_with_spans:
            for i in range(word_info['start_char_idx'], word_info['end_char_idx']):
                char_to_word_info[i] = word_info

        # Map spans to words
        for region, region_spans in spans.items():
            for start, end in region_spans:
                unique_words_for_span = []
                for char_idx in range(start, end):
                    if char_idx in char_to_word_info:
                        word_obj = char_to_word_info[char_idx]
                        if word_obj not in unique_words_for_span:
                            unique_words_for_span.append(word_obj)
                region_words[region].extend(unique_words_for_span)
        
        return region_words

    def generate_training_manifest(self, region_words: Dict[str, List[Dict]], words_with_spans: List[Dict]) -> Dict:
        """Generate training manifest in the required format with BIO tagging."""
        manifest = {
            "regions": [],
            "tokens": []
        }

        # Create a mapping of character indices to word_info for quick lookup
        # This will be used to map tokens from LayoutLMv3Processor to actual words
        full_text_words_map = {word['start_char_idx']: word for word in words_with_spans}

        # Initialize all words with 'O' (Outside) label
        # Use a list of dictionaries to store tokens, so we can modify labels easily
        tokens_with_labels = []
        for word_info in words_with_spans:
            tokens_with_labels.append({
                "text": word_info["text"],
                "box": word_info["box"],
                "label": "O" # Default to Outside
            })

        # Iterate through regions and apply BIO tags
        for region_type, words_in_region in region_words.items():
            if not words_in_region:
                continue

            # Sort words by their start_char_idx to ensure correct B-I-O sequence
            words_in_region.sort(key=lambda w: w['start_char_idx'])

            is_first_word_in_region = True
            for word in words_in_region:
                # Find the corresponding token in tokens_with_labels and apply BIO tag
                # This is a simplified matching; more robust would involve token-level alignment
                for i, token_entry in enumerate(tokens_with_labels):
                    if token_entry["text"] == word["text"] and token_entry["box"] == word["box"]:
                        if is_first_word_in_region:
                            tokens_with_labels[i]["label"] = f"B-{region_type}"
                            is_first_word_in_region = False
                        else:
                            tokens_with_labels[i]["label"] = f"I-{region_type}"
                        # Break after finding and labeling the first match for this word
                        break
            
            # Add regions (union of word boxes) to manifest
            try:
                x0 = min(w["box"][0] for w in words_in_region)
                y0 = min(w["box"][1] for w in words_in_region)
                x1 = max(w["box"][2] for w in words_in_region)
                y1 = max(w["box"][3] for w in words_in_region)
            except ValueError: # Handle case where words_in_region might be empty for some reason
                self.logger.warning(f"No words found for region {region_type} during manifest generation. Skipping region.")
                continue
            
            manifest["regions"].append({
                "class": region_type,
                "box": [x0, y0, x1, y1],
                "words": [w["text"] for w in words_in_region]
            })

        # Add all tokens with their assigned BIO labels to the manifest
        manifest["tokens"] = tokens_with_labels
        
        return manifest

    def process_invoice(self, file_path: str) -> Dict:
        """Process a single invoice and return its manifest entry."""
        # Load OCR JSON
        try:
            with open(file_path, 'r') as f:
                ocr_json = json.load(f)
        except Exception as e:
            logger.error(f"Error loading OCR JSON from {file_path}: {e}")
            return None
        
        # Extract text and get word information with character spans
        full_text, words_with_spans = self.extract_text_from_ocr(ocr_json)
        
        logger.info(f"\\nExtracted text from {file_path}:\\n{full_text}\\n")
        
        # Find spans using spatial proximity and regex fallback
        spans = self.find_matches(words_with_spans, full_text) # Pass full_text here too!
        
        logger.info("\\nMatched spans:")
        for region, region_spans in spans.items():
            if region_spans:
                # For debugging, log the actual text of the first found span
                first_span_text = full_text[region_spans[0][0]:region_spans[0][1]]
                logger.info(f"{region}: {region_spans[0]} -> '{first_span_text}'")
            else:
                logger.info(f"{region}: No matches found")
        
        # Align spans to words
        region_words = self.align_spans_to_words(full_text, spans, words_with_spans)
        
        # Generate manifest
        manifest = self.generate_training_manifest(region_words, words_with_spans)
        
        return manifest

    def process_all_invoices(self) -> List[Dict]:
        """Process all invoices in the directory."""
        manifests = []
        for filename in os.listdir(self.json_dir):
            if filename.endswith('.json') and not filename.startswith('training_manifest'):
                file_path = os.path.join(self.json_dir, filename)
                logger.info(f"Processing {filename}...")
                
                manifest = self.process_invoice(file_path)
                if manifest:
                    manifest["file_name"] = filename
                    manifests.append(manifest)
                else:
                    logger.error(f"Failed to process {filename}")
        
        return manifests

def main():
    # Get the absolute path of the current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_dir = os.path.join(current_dir, "ocr_json") # Updated path to point to the ocr_json directory
    output_file = os.path.join(current_dir, "training_manifest.json")
    
    generator = LabelGenerator(json_dir)
    manifests = generator.process_all_invoices()
    
    # Save the combined manifest
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(manifests, f, indent=2)
    
    logger.info(f"Generated training manifest with {len(manifests)} invoices")
    logger.info(f"Manifest saved to {output_file}")

if __name__ == "__main__":
    main()