import os
import json
import torch
from transformers import LayoutLMv3ForTokenClassification, LayoutLMv3Processor, TrainingArguments, Trainer, LayoutLMv3Config
from dataset import LayoutLMv3Dataset
from train import collate_fn
import safetensors.torch # Import safetensors

def test_training_setup():
    # Setup absolute paths
    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_dir = current_dir
    image_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "media/invoices")

    # Initialize processor
    processor = LayoutLMv3Processor.from_pretrained("microsoft/layoutlmv3-base", apply_ocr=False)
    
    # Create dataset
    dataset = LayoutLMv3Dataset(json_dir=json_dir, image_dir=image_dir, processor=processor)
    
    print(f"Dataset size: {len(dataset)}")
    
    # Test a single sample
    if len(dataset) > 0:
        sample = dataset[0]
        print("\nSample shapes:")
        print(f"input_ids: {sample['input_ids'].shape}")
        print(f"attention_mask: {sample['attention_mask'].shape}")
        print(f"bbox: {sample['bbox'].shape}")
        print(f"labels: {sample['labels'].shape}")
        if sample["pixel_values"] is not None:
            print(f"pixel_values: {sample['pixel_values'].shape}")
        
        # Test collate function
        batch = [sample, sample]  # Create a small batch
        collated = collate_fn(batch)
        
        print("\nCollated batch shapes:")
        print(f"input_ids: {collated['input_ids'].shape}")
        print(f"attention_mask: {collated['attention_mask'].shape}")
        print(f"bbox: {collated['bbox'].shape}")
        print(f"labels: {collated['labels'].shape}")
        if collated["pixel_values"] is not None:
            print(f"pixel_values: {collated['pixel_values'].shape}")
        
        # Print some sample text and labels
        print("\nSample text:")
        tokens = sample["input_ids"].tolist()
        decoded_text = processor.tokenizer.decode(tokens, skip_special_tokens=True)
        print(decoded_text[:200] + "...")
        
        print("\nSample labels:")
        print(sample["labels"][:20].tolist())
        
        return True
    else:
        print("No data files found in the specified JSON directory.")
        return False

def test_inference():
    print("\n--- Testing Model Inference ---")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_dir = current_dir
    image_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "media/invoices")

    processor = LayoutLMv3Processor.from_pretrained("microsoft/layoutlmv3-base", apply_ocr=False, local_files_only=True)

    # Load the training manifest to get label information for id2label mapping
    with open(os.path.join(json_dir, "training_manifest.json"), "r") as f:
        training_manifest = json.load(f)

    unique_classes = set()
    for item in training_manifest:
        for region in item["regions"]:
            unique_classes.add(region["class"])

    # Create label2id mapping, ensuring 'O' (Outside) is always mapped to 0
    label2id = {"O": 0}
    current_id = 1
    for label in sorted(unique_classes):
        if label != "O": # Ensure 'O' is not duplicated if somehow in manifest
            label2id[label] = current_id
            current_id += 1
            
    id2label = {idx: label for label, idx in label2id.items()}

    num_labels = len(label2id)

    # Load the trained model explicitly
    try:
        project_root = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
        base_results_dir = os.path.join(project_root, "results")

        config_path = os.path.join(base_results_dir, "checkpoint-6", "config.json")
        model_path = os.path.join(base_results_dir, "checkpoint-6", "model.safetensors") 
        
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found at: {config_path}")
        if not os.path.exists(model_path):
            model_path_pt = os.path.join(base_results_dir, "checkpoint-6", "pytorch_model.bin")
            if os.path.exists(model_path_pt):
                model_path = model_path_pt
            else:
                raise FileNotFoundError(f"Model file not found at: {model_path} or {model_path_pt}")

        config = LayoutLMv3Config.from_pretrained(config_path)
        config.id2label = id2label
        config.label2id = label2id

        model = LayoutLMv3ForTokenClassification(config)
        
        if model_path.endswith(".safetensors"):
            state_dict = safetensors.torch.load_file(model_path)
        else:
            state_dict = torch.load(model_path, map_location=torch.device('cpu'), weights_only=False)
            
        model.load_state_dict(state_dict)
        model.eval()
        print("Successfully loaded trained model from ./results/checkpoint-6")
    except Exception as e:
        print(f"Error loading trained model: {e}. Ensure training was successful and results directory exists.")
        return False

    # Create dataset from generated OCR JSONs
    test_data_files = [f for f in os.listdir(json_dir) if f.endswith('_ocr_json.json') and f != 'training_manifest.json' and f != 'invoice_69_ocr_json.json']
    if not test_data_files:
        print("No new OCR JSON files found for testing inference. Please ensure generate_ocr_jsons_from_images.py was run.")
        return False

    print(f"Found {len(test_data_files)} OCR JSON files for inference.")

    # Process each test file individually
    for json_file in test_data_files:
        file_path = os.path.join(json_dir, json_file)
        print(f"\nProcessing {json_file}...")
        try:
            with open(file_path, 'r') as f:
                ocr_json = json.load(f)
            
            # Get the base name without _ocr_json.json
            base_name = json_file.replace('_ocr_json.json', '')
            
            # Try to find the original image in the Invoice Templates directory
            image_path = None
            for ext in [".png", ".jpg", ".jpeg", ".webp", ".pdf"]:
                potential_path = os.path.join("Invoice Templates", base_name + ext)
                if os.path.exists(potential_path):
                    image_path = potential_path
                    break
            
            if not image_path:
                print(f"Warning: Original image for {json_file} not found in Invoice Templates. Using dummy image.")
            
            from data_utils import ocr_json_to_layoutlm_inputs
            inputs = ocr_json_to_layoutlm_inputs(ocr_json, image_path=image_path)

            if inputs is None or not inputs["input_ids"].numel():
                print(f"Skipping {json_file} due to empty or invalid input.")
                continue

            inputs = {k: v.to(model.device) for k, v in inputs.items() if v is not None}
            
            with torch.no_grad():
                outputs = model(**inputs)

            predictions = outputs.logits.argmax(dim=-1).squeeze().tolist()
            tokens = inputs["input_ids"].squeeze().tolist()
            words = processor.tokenizer.convert_ids_to_tokens(tokens)

            # Group entities by type
            entities = {}
            current_entity = []
            current_label = None

            for i, (pred_id, token) in enumerate(zip(predictions, words)):
                if pred_id != label2id["O"] and i < len(words):
                    label = id2label[pred_id]
                    
                    # Handle subword tokens
                    if token.startswith("##"):
                        if current_entity:
                            current_entity.append(token[2:])
                    else:
                        if current_entity:
                            if current_label not in entities:
                                entities[current_label] = []
                            entities[current_label].append("".join(current_entity))
                            current_entity = []
                        current_label = label
                        current_entity = [token]

            # Add the last entity if exists
            if current_entity and current_label:
                if current_label not in entities:
                    entities[current_label] = []
                entities[current_label].append("".join(current_entity))

            # Print extracted entities in a structured format
            print("\nExtracted Entities:")
            for label, values in entities.items():
                print(f"\n{label}:")
                for value in values:
                    print(f"  - {value}")

        except Exception as e:
            print(f"Error processing {json_file} for inference: {e}")
            
    return True

if __name__ == "__main__":
    print("Testing training setup...")
    success_setup = test_training_setup()
    
    if success_setup:
        test_inference()
    else:
        print("Training setup test failed, skipping inference test.") 