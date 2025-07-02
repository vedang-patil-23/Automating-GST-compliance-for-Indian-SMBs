# backend/debug_parsing.py

import re
from invoices.models import Invoice, LineItem
from django.db import transaction

# Raw OCR text from Invoice #30 template for debugging
raw_ocr_text = """
Tax Invoice

IRN fef1df90406b928db26a62f816debc9bb5256d9375e6-
0dc4226653cc23a8c595

Ack No 112010036563310

Ack Date: 21-Dec-20

e-Invoice

Surabhi Hardwares, Bangalore
HSR Layout

Bangalore

GSTIN/UIN: 29AACCT3705E000
State Name : Karnataka, Code : 29

Invoice No.
SHB/456/20

Dated
20-Dec-20

Delivery Note

Mode/Terms of Payment

Consignee (Ship to)
Kiran Enterprises

Reference No. & Date.

Other References

Buyer's Order No.

Dated

12th Cross
GSTIN/UIN : 29AAFFC8126N1ZZ Dispatch Doc No Delivery Note Date
State Name : Karnataka, Code : 29
Buyer (Bill to) Dispatched through Destination
Kiran Enterprises
42th Cross Terms of Delivery
GSTIN/UIN : 29AAFFC8126N1ZZ
State Name : Karnataka, Code : 29
Sl Description of Goods HSN/SAC | Quantity Rate per | Disc. % Amount
No.
1 |12MmM** 1005 7No| 500.00] No 3,500.00
CGST| 315.00
SGST| 315.00
Total 7 No = 4,130.00
Amount Chargeable (in words) E&OE
Indian Rupee Four Thousand One Hundred Thirty Only
HSN/SAC Taxable Central Tax State Tax Total
Value Rate | Amount_| Rate | Amount_ | Tax Amount
1005 3,500.00 9% 315.00 9% 315.00 630.00
Total 3,500.00 315.00 315.00 630.00

Tax Amount (in words) : Indian Rupee Six Hundred Sixty Only

Declaration

We declare that this invoice shows the actual price of the
goods described and that all particulars are true and
correct.

for Surabhi Hardwares, Bangalore

Authorised Signatory

This is a Computer Generated Invoice
"""

def debug_parse_invoice_data(raw_text):
    """
    Debug function to parse structured data from raw OCR text.
    """
    # Create a dummy Invoice object for testing purposes
    # This object won't be saved to the database unless you explicitly call .save()
    # and are within an atomic transaction or outside this script.
    # We need it to call invoice.line_items.all().delete() and to set attributes.
    # Make sure your database is set up and migrations applied if running this in a real shell.
    try:
        # Attempt to use an existing invoice if ID 999 exists, otherwise create one
        invoice, created = Invoice.objects.get_or_create(id=999, defaults={'status':'pending', 'ocr_data':{'text':''}} )
        invoice.ocr_data = { 'text': raw_text }
        invoice.status = 'ocr_complete' # Start at ocr_complete for parsing debug
        print(f"--- Debugging Invoice ID: {invoice.id}, Status: {invoice.status} ---")

    except Exception as e:
        print(f"Error creating or getting dummy invoice: {e}")
        return

    lines = raw_text.splitlines()

    # --- Parsing Logic (Copied from parsers.py, with added prints) ---

    # Extract Invoice Number
    print("\n--- Extracting Invoice Number ---")
    invoice_number_match = re.search(r'(?:Invoice No|Bill No|TAX INVOICE)[.:\s]*([\w\d/-]+)', raw_text, re.IGNORECASE)
    print(f"Regex pattern: {(invoice_number_match.re.pattern if invoice_number_match else 'Not matched')}")
    print(f"Match object: {invoice_number_match}")
    if invoice_number_match:
        invoice.invoice_number = invoice_number_match.group(1).strip()
        print(f"Extracted Invoice Number: {invoice.invoice_number}")
    else:
        invoice.invoice_number = ''
        print("Invoice Number not found.")

    # Extract Invoice Date
    print("\n--- Extracting Invoice Date ---")
    invoice_date_match = re.search(r'(?:Date|Dated)[.:\s]*([\d]{1,2}[-/\.\s][\d]{1,2}[-/\.\s][\d]{2,4}|[\d]{4}[-/\.\s][\d]{1,2}[-/\.\s][\d]{1,2}|[\d]{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+[\d]{4})', raw_text, re.IGNORECASE)
    print(f"Regex pattern: {(invoice_date_match.re.pattern if invoice_date_match else 'Not matched')}")
    print(f"Match object: {invoice_date_match}")
    if invoice_date_match:
        invoice.invoice_date = invoice_date_match.group(1).strip() # Store as string for now
        print(f"Extracted Invoice Date: {invoice.invoice_date}")
    else:
        invoice.invoice_date = ''
        print("Invoice Date not found.")

    # Extract Seller GSTIN
    print("\n--- Extracting Seller GSTIN ---")
    seller_gstin_match = re.search(r'(?:Seller GSTIN|GSTIN/UIN)[.:\s]*([\w\d]{15})', raw_text, re.IGNORECASE)
    print(f"Regex pattern: {(seller_gstin_match.re.pattern if seller_gstin_match else 'Not matched')}")
    print(f"Match object: {seller_gstin_match}")
    if seller_gstin_match:
         invoice.seller_gstin = seller_gstin_match.group(1).strip()
         print(f"Extracted Seller GSTIN: {invoice.seller_gstin}")
    else:
        invoice.seller_gstin = ''
        print("Seller GSTIN not found.")

    # Extract Buyer Details
    print("\n--- Extracting Buyer Name ---")
    buyer_name_match = re.search(r'(?:Consignee \(Ship to\)|Buyer \(Bill to\)|Bill To)[.:\s]*(.+?)\n', raw_text, re.IGNORECASE | re.DOTALL)
    print(f"Regex pattern: {(buyer_name_match.re.pattern if buyer_name_match else 'Not matched')}")
    print(f"Match object: {buyer_name_match}")
    if buyer_name_match:
        invoice.buyer_name = buyer_name_match.group(1).strip()
        print(f"Extracted Buyer Name: {invoice.buyer_name}")
    else:
        invoice.buyer_name = ''
        print("Buyer Name not found.")

    print("\n--- Extracting Buyer GSTIN ---")
    buyer_gstin_match = re.search(r'Buyer GSTIN[.:\s]*([\w\d]{15})|GSTIN/UIN[.:\s]*.*Buyer\s*.*?([\w\d]{15})', raw_text, re.IGNORECASE | re.DOTALL)
    print(f"Regex pattern: {(buyer_gstin_match.re.pattern if buyer_gstin_match else 'Not matched')}")
    print(f"Match object: {buyer_gstin_match}")
    if buyer_gstin_match:
         try:
            # Try group 1 first (explicit Buyer GSTIN), then group 2 (GSTIN/UIN near Buyer)
            invoice.buyer_gstin = next(item for item in buyer_gstin_match.groups() if item is not None).strip()
            print(f"Extracted Buyer GSTIN: {invoice.buyer_gstin}")
         except StopIteration:
            invoice.buyer_gstin = ''
            print("Buyer GSTIN not found.")
    else:
        invoice.buyer_gstin = ''
        print("Buyer GSTIN not found.")

    # Extract Total Tax Amount
    print("\n--- Extracting Total Tax Amount ---")
    cgst_match = re.search(r'CGST[|:\s]*([\d]+(?:.[\d]+)?)', raw_text, re.IGNORECASE)
    sgst_match = re.search(r'SGST[|:\s]*([\d]+(?:.[\d]+)?)', raw_text, re.IGNORECASE)
    igst_match = re.search(r'IGST[|:\s]*([\d]+(?:.[\d]+)?)', raw_text, re.IGNORECASE)
    print(f"CGST Match: {cgst_match}, SGST Match: {sgst_match}, IGST Match: {igst_match}")

    total_tax_amount = 0
    if cgst_match: total_tax_amount += float(cgst_match.group(1))
    if sgst_match: total_tax_amount += float(sgst_match.group(1))
    if igst_match: total_tax_amount += float(igst_match.group(1))

    if total_tax_amount > 0:
         invoice.total_tax_amount = total_tax_amount
         print(f"Calculated Total Tax Amount (from CGST/SGST/IGST): {invoice.total_tax_amount}")
    else:
        invoice.total_tax_amount = None # Or 0.0, depending on desired representation
        print("Total Tax Amount not calculated from GST components.")
        # Fallback to general Total Tax / Tax Amount if specific GST amounts not found
        general_tax_match = re.search(r'(?:Total Tax|Tax Amount)[.:\s]*([\d]+(?:.[\d]+)?)', raw_text, re.IGNORECASE)
        print(f"Fallback General Tax Match: {general_tax_match}")
        if general_tax_match:
             try:
                invoice.total_tax_amount = float(general_tax_match.group(1))
                print(f"Extracted Total Tax Amount (fallback): {invoice.total_tax_amount}")
             except ValueError:
                print("Could not convert fallback tax amount to float.")
                pass # Keep as None or previous value on error


    # Extract Grand Total
    print("\n--- Extracting Grand Total ---")
    grand_total_match = re.search(r'(?:Grand Total|Total Amount Payable|Net Amount|Total Value|Total)[.:\s]*([Rs.$]*\s*[\d,]+\.[\d]{2})', raw_text, re.IGNORECASE)
    print(f"Regex pattern: {(grand_total_match.re.pattern if grand_total_match else 'Not matched')}")
    print(f"Match object: {grand_total_match}")
    if grand_total_match:
        try:
            # Clean the matched string and handle commas/periods for thousands/decimals
            amount_str = grand_total_match.group(1).replace('Rs.', '').replace('$', '').replace(',', '').strip()
            invoice.total_amount = float(amount_str)
            print(f"Extracted Grand Total: {invoice.total_amount}")
        except ValueError:
            invoice.total_amount = None
            print("Could not convert grand total amount to float.")
            pass
    else:
        invoice.total_amount = None
        print("Grand Total not found.")


    # --- Line Item Parsing (Attempting to match table rows with '|') ---
    print("\n--- Parsing Line Items ---")
    potential_line_items_data = []
    # Regex for table row with '|' separators:
    # Sl No | Description | HSN/SAC | Qty | Rate | Disc % | Amount
    # This pattern specifically looks for the columns separated by '|' and captures the data within them.
    line_item_pattern = re.compile(
        r'^\s*(\\d+)\s*\\|\\s*(.+?)\s*\\|\\s*([\\w\\d]*)\s*\\|\\s*(\\d+(?:\\.\\d+)?)\\s*\\|\\s*(\\d+(?:\\.\\d+)?)\\s*\\|\\s*([\\d\\.]*)\\s*\\|\\s*(\\d+(?:\\.\\d+)?)\\s*$',
        re.IGNORECASE
    )

    print(f"Line item regex pattern: {line_item_pattern.pattern}")
    for i, line in enumerate(lines):
        print(f"Checking line {i+1}: {line}")
        match = line_item_pattern.match(line)
        print(f"Match object for line {i+1}: {match}")
        if match:
            try:
                # Groups: (Sl No), (Description), (HSN/SAC), (Quantity), (Qty decimal), (Rate), (Rate decimal), (Disc %), (Amount), (Amount decimal)
                groups = match.groups()
                print(f"Match groups for line {i+1}: {groups}")

                # Basic assignment - needs robust validation
                sl_no = int(groups[0]) # Not currently stored in model, but captured
                description = groups[1].strip()
                hsn_sac = groups[2].strip()
                quantity = float(groups[3])
                rate = float(groups[5])
                amount = float(groups[8])

                item_data = {
                    'description': description,
                    'quantity': quantity,
                    'rate': rate,
                    'amount': amount,
                    'hsn_sac': hsn_sac,
                }
                potential_line_items_data.append(item_data)
                print(f"Parsed line item data: {item_data}")
            except (ValueError, IndexError) as e:
                print(f"Could not parse line item from line: {line} - {e}")
                pass # Skip this line item

    print(f"\nPotential Line Items Data: {potential_line_items_data}")

    # In a real task, you would save the invoice and create line items here within a transaction.
    # For debugging, we just print the results.
    invoice.line_items.all().delete() # Clean up dummy line items if they exist
    for item_data in potential_line_items_data:
         # Create LineItem objects associated with the dummy invoice
         LineItem.objects.create(invoice=invoice, **item_data)


    invoice.status = 'parsing_complete' # Mark as complete for debugging
    # invoice.save() # Don't save the dummy invoice to avoid cluttering the DB unless intended

    print("\n--- Debugging Complete ---")
    print(f"Final Invoice Data (not necessarily saved):\n" \
          f"  Invoice Number: {invoice.invoice_number}\n" \
          f"  Invoice Date: {invoice.invoice_date}\n" \
          f"  Seller GSTIN: {invoice.seller_gstin}\n" \
          f"  Buyer Name: {invoice.buyer_name}\n" \
          f"  Buyer GSTIN: {invoice.buyer_gstin}\n" \
          f"  Total Tax Amount: {invoice.total_tax_amount}\n" \
          f"  Total Amount: {invoice.total_amount}\n" \
          f"  Line Items Count: {invoice.line_items.count()}\n" \
          f"  First Line Item Data: {invoice.line_items.first().__dict__ if invoice.line_items.first() else 'None'}")

# To run this script from your backend directory:
# python manage.py shell < debug_parsing.py
debug_parse_invoice_data(raw_ocr_text) 