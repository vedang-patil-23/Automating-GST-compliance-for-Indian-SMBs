import os
import json
import torch
from torch.utils.data import Dataset
from data_utils import ocr_json_to_layoutlm_inputs

class LayoutLMv3Dataset(Dataset):
    def __init__(self, json_dir, image_dir=None, processor=None):
        self.json_dir = json_dir
        self.image_dir = image_dir
        self.processor = processor
        # Only include actual OCR JSON files, not the manifest
        self.data_files = [f for f in os.listdir(json_dir) if f.endswith('.json') and f != 'training_manifest.json']
        
        # Load training manifest
        manifest_path = os.path.join(json_dir, "training_manifest.json")
        with open(manifest_path, 'r', encoding='utf-8') as f:
            self.training_manifest = json.load(f)
            
        # Create a mapping of file names to their annotations
        self.annotations = {}
        all_unique_classes = set([item["label"] for manifest_entry in self.training_manifest for item in manifest_entry["tokens"]])
        
        # Create label2id mapping, ensuring 'O' (Outside) is always mapped to 0
        self.label2id = {"O": 0}
        current_id = 1
        for label in sorted(all_unique_classes):
            if label != "O":
                self.label2id[label] = current_id
                current_id += 1
                
        self.id2label = {idx: label for label, idx in self.label2id.items()}

        for item in self.training_manifest:
            file_name = os.path.basename(item.get("file_name", ""))
            if file_name:
                self.annotations[file_name] = item["tokens"] # Store tokens directly

    def __len__(self):
        return len(self.data_files)

    def __getitem__(self, idx):
        file_name = self.data_files[idx]
        json_path = os.path.join(self.json_dir, file_name)

        with open(json_path, 'r', encoding='utf-8') as f:
            ocr_json = json.load(f)

        image_path = None
        if self.image_dir:
            # Assuming image file name matches JSON file name (e.g., invoice_69.json -> invoice_69.jpg)
            # You might need to adjust this logic based on your actual file naming convention
            base_name = os.path.splitext(file_name)[0]
            # Attempt common image extensions
            for ext in ['.jpg', '.jpeg', '.png', '.pdf']:
                potential_image_path = os.path.join(self.image_dir, base_name + ext)
                if os.path.exists(potential_image_path):
                    image_path = potential_image_path
                    break
            if not image_path:
                print(f"Warning: No image found for {file_name} in {self.image_dir}. Processing text-only.")

        # Get the encoding from OCR JSON
        encoding = ocr_json_to_layoutlm_inputs(ocr_json, image_path)

        # Ensure that if encoding is empty, we handle it gracefully
        if encoding is None or encoding["input_ids"].numel() == 0:
            print(f"Warning: Skipping {file_name} due to empty or invalid OCR data.")
            # If the input_ids is empty, the label should also be empty.
            return {
                "input_ids": torch.tensor([]).long(),
                "attention_mask": torch.tensor([]).long(),
                "bbox": torch.tensor([[]]).long(),
                "pixel_values": torch.tensor([[[[]]]]).float(),
                "labels": torch.tensor([]).long()
            }

        # Get annotations for this file (now containing BIO tokens)
        file_annotations_tokens = self.annotations.get(file_name, [])
        
        # Initialize labels for all tokens in the sequence to 'O' (Outside)
        labels = torch.full((encoding["input_ids"].shape[1],), self.label2id["O"], dtype=torch.long)

        # Get word_ids for aligning tokens to original words
        word_ids = encoding["word_ids"].squeeze(0).tolist() # Access directly

        previous_word_idx = None
        current_word_annotation = None

        # Iterate through the model's tokens and assign labels based on BIO annotations
        for token_idx, word_idx in enumerate(word_ids):
            if word_idx is None: # Special tokens like [CLS], [SEP]
                labels[token_idx] = self.label2id["O"]
                continue
            
            if word_idx != previous_word_idx:
                # New word, find its annotation
                current_word_annotation = None
                for ann_token in file_annotations_tokens:
                    # Try to match by text and box for robustness
                    # This is a simplified match, a more robust solution might need character offsets or fuzzy matching
                    if ann_token["text"] == encoding.words[word_idx] and ann_token["box"] == encoding.boxes[word_idx]:
                        current_word_annotation = ann_token
                        break
            
            if current_word_annotation:
                label_tag = current_word_annotation["label"]
                labels[token_idx] = self.label2id.get(label_tag, self.label2id["O"])
            
            previous_word_idx = word_idx

        # Prepare the output
        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "bbox": encoding["bbox"].squeeze(0),
            "pixel_values": encoding["pixel_values"].squeeze(0) if "pixel_values" in encoding else None,
            "labels": labels
        }

# Example usage (for testing):
if __name__ == "__main__":
    from transformers import LayoutLMv3Processor
    
    # Assuming your current working directory is 'backend'
    json_dir = "invoices/ml_layoutlm"
    # For this example, if you have invoice images in media/invoices/
    image_dir = "media/invoices"

    # Initialize the processor (same as in data_utils)
    processor = LayoutLMv3Processor.from_pretrained("microsoft/layoutlmv3-base", apply_ocr=False)

    dataset = LayoutLMv3Dataset(json_dir=json_dir, image_dir=image_dir, processor=processor)

    print(f"Dataset size: {len(dataset)}")

    if len(dataset) > 0:
        sample = dataset[0]
        print(f"Sample input_ids shape: {sample['input_ids'].shape}")
        print(f"Sample attention_mask shape: {sample['attention_mask'].shape}")
        print(f"Sample bbox shape: {sample['bbox'].shape}")
        print(f"Sample labels shape: {sample['labels'].shape}")
        if sample["pixel_values"] is not None:
            print(f"Sample pixel_values shape: {sample['pixel_values'].shape}")
        else:
            print("No pixel_values in sample (image_path was not found or provided).")

        # Decode some tokens to see the text
        tokens = sample["input_ids"].tolist()
        decoded_text = processor.tokenizer.decode(tokens, skip_special_tokens=True)
        print(f"\nDecoded text for first sample:\n{decoded_text[:500]}...")
        
        # Print some labels
        print("\nFirst few labels:", sample["labels"][:10].tolist())

    else:
        print("No data files found in the specified JSON directory.") 