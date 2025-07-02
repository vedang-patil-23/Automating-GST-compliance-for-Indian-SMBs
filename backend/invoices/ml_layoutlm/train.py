import os
import json
import torch
from transformers import LayoutLMv3ForTokenClassification, LayoutLMv3Processor, TrainingArguments, Trainer
from torch.utils.data import DataLoader
from dataset import LayoutLMv3Dataset

# Define the path to your JSON and (optional) image directories using absolute paths
current_dir = os.path.dirname(os.path.abspath(__file__))
json_dir = current_dir
image_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "media/invoices")  # Adjust if your image path is different

# Load the training manifest to get label information
with open(os.path.join(json_dir, "training_manifest.json"), "r") as f:
    training_manifest = json.load(f)

# Get unique classes from the training manifest
unique_classes = set()
for item in training_manifest:
    for region in item["regions"]:
        unique_classes.add(region["class"])

# Initialize the processor
processor = LayoutLMv3Processor.from_pretrained("microsoft/layoutlmv3-base", apply_ocr=False)

# Load the dataset
dataset = LayoutLMv3Dataset(json_dir=json_dir, image_dir=image_dir, processor=processor)

# Get label mappings from the dataset (now handles BIO tags)
label2id = dataset.label2id
id2label = dataset.id2label
num_labels = len(label2id)

# Define a data collator that handles labels
def collate_fn(batch):
    # Filter out empty samples that might result from processing errors
    batch = [item for item in batch if item["input_ids"].numel() > 0]
    
    if not batch:
        return None

    # Pad input_ids, attention_mask, bbox, and labels
    input_ids = [item["input_ids"] for item in batch]
    attention_mask = [item["attention_mask"] for item in batch]
    bbox = [item["bbox"] for item in batch]
    pixel_values = [item["pixel_values"] for item in batch]
    labels = [item["labels"] for item in batch]

    # Use processor.tokenizer.pad to handle padding
    padded_inputs = processor.tokenizer.pad(
        {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "bbox": bbox,
            "labels": labels
        },
        padding=True,
        return_tensors="pt"
    )
    
    # Handle pixel values
    padded_inputs["pixel_values"] = torch.stack(pixel_values) if pixel_values[0] is not None else None

    return padded_inputs

# Load the model with proper number of labels
model = LayoutLMv3ForTokenClassification.from_pretrained(
    "microsoft/layoutlmv3-base",
    num_labels=num_labels,
    id2label=id2label,
    label2id=label2id
)

# Explicitly set num_labels in the model config to ensure it's saved correctly
model.config.num_labels = num_labels

# Define training arguments
training_args = TrainingArguments(
    output_dir="./results",
    per_device_train_batch_size=4,
    num_train_epochs=3,
    save_steps=500,
    logging_steps=100,
    learning_rate=5e-5,
    weight_decay=0.01,
    warmup_steps=500,
    no_cuda=True if not torch.cuda.is_available() else False
)

# Initialize Trainer
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=dataset,
    data_collator=collate_fn,
)

if __name__ == "__main__":
    print(f"Dataset size: {len(dataset)}")
    print(f"Number of unique classes: {len(label2id)}")
    print("Classes:", sorted(unique_classes))
    print("Starting training...")
    trainer.train()
    print("Training complete!") 