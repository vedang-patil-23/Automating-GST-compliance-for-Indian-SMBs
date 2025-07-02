import os
import json
import pytesseract
from PIL import Image
import cv2
import numpy as np

# Define paths
IMAGE_TEMPLATES_DIR = "Invoice Templates"
OCR_JSON_OUTPUT_DIR = "backend/invoices/ml_layoutlm"

def normalize_box(box, width, height):
    return [
        int(1000 * (box[0] / width)),
        int(1000 * (box[1] / height)),
        int(1000 * (box[2] / width)),
        int(1000 * (box[3] / height)),
    ]

def generate_ocr_json_from_image(image_path, output_dir):
    try:
        # Open the image using PIL
        image = Image.open(image_path).convert("RGB")
        image_width, image_height = image.size

        # Perform OCR using pytesseract
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

        # Initialize JSON structure
        ocr_json = {
            "pages": [
                {
                    "page_num": 1,
                    "width": image_width,
                    "height": image_height,
                    "blocks": []
                }
            ]
        }

        # Group words into lines and blocks (a simplified approach for now)
        # In a real scenario, you might want more sophisticated block/line detection
        current_block = {"bbox": [0, 0, image_width, image_height], "lines": []}
        current_line = {"bbox": [0, 0, image_width, image_height], "words": []}

        for i in range(len(data["text"])):
            word_text = data["text"][i].strip()
            if not word_text:
                continue

            # Extract bounding box from tesseract data
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            bbox = [x, y, x + w, y + h]

            # Normalize bounding box to 1000x1000 scale
            normalized_bbox = normalize_box(bbox, image_width, image_height)

            current_line["words"].append({
                "text": word_text,
                "bbox": normalized_bbox # Store normalized bbox
            })

        # Add the last line and block
        if current_line["words"]:
            # Calculate bbox for the entire line (simple union of word bboxes)
            all_x = [word["bbox"][0] for word in current_line["words"]]
            all_y = [word["bbox"][1] for word in current_line["words"]]
            all_x2 = [word["bbox"][2] for word in current_line["words"]]
            all_y2 = [word["bbox"][3] for word in current_line["words"]]
            if all_x and all_y and all_x2 and all_y2:
                current_line["bbox"] = [
                    min(all_x),
                    min(all_y),
                    max(all_x2),
                    max(all_y2)
                ]
            current_block["lines"].append(current_line)
        
        if current_block["lines"]:
            # Calculate bbox for the entire block
            all_x = [line["bbox"][0] for line in current_block["lines"]]
            all_y = [line["bbox"][1] for line in current_block["lines"]]
            all_x2 = [line["bbox"][2] for line in current_block["lines"]]
            all_y2 = [line["bbox"][3] for line in current_block["lines"]]
            if all_x and all_y and all_x2 and all_y2:
                current_block["bbox"] = [
                    min(all_x),
                    min(all_y),
                    max(all_x2),
                    max(all_y2)
                ]
            ocr_json["pages"][0]["blocks"].append(current_block)

        # Save the JSON file
        image_filename = os.path.basename(image_path)
        output_filepath = os.path.join(output_dir, f"{os.path.splitext(image_filename)[0]}_ocr_json.json")
        
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(ocr_json, f, indent=4, ensure_ascii=False)
        print(f"Successfully generated OCR JSON for {image_path} to {output_filepath}")

    except Exception as e:
        print(f"Error processing {image_path}: {e}")

if __name__ == "__main__":
    # Ensure output directory exists
    os.makedirs(OCR_JSON_OUTPUT_DIR, exist_ok=True)

    # Process all image files in the templates directory
    for filename in os.listdir(IMAGE_TEMPLATES_DIR):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.pdf')):
            image_path = os.path.join(IMAGE_TEMPLATES_DIR, filename)
            generate_ocr_json_from_image(image_path, OCR_JSON_OUTPUT_DIR) 