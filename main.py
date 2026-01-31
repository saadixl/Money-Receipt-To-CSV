import base64
import io
import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from openai import OpenAI
from pdf2image import convert_from_path
import pandas as pd

INPUT_DIR = Path("./receipts")
OUTPUT_FILE = "receipt_data.csv"


def load_config():
    """Load config from environment (.env). All receipt-related values are optional."""
    additional = os.environ.get("ADDITIONAL_AMOUNT_LABEL", "Additional Amount").strip()
    return {
        "money_unit": os.environ.get("MONEY_UNIT", "USD"),
        "sender_name": os.environ.get("SENDER_NAME", "a sender"),
        "amount_label": os.environ.get("AMOUNT_LABEL", "Amount"),
        "additional_amount_label": additional if additional else None,
    }


def build_extraction_prompt(config: dict) -> str:
    """Build the extraction prompt from config (money unit, sender name, field labels)."""
    unit = config["money_unit"]
    sender = config["sender_name"]
    amount_label = config["amount_label"]
    additional_label = config.get("additional_amount_label")

    lines = [
        f"This is a money transfer receipt (e.g., from {sender}).",
        "",
        "Extract the following fields and return ONLY valid JSON with no extra text:",
        "",
        '1. **Date** - Look in the "Transaction\'s Details" section (bottom left). Find "Cr Date" or "Pay Date". Format is YYYY-MM-DDThh:mm:ss.abc (e.g., 2020-01-15T10:30:00.000). Use "N/A" if not found.',
        "",
        f'2. **{amount_label}** - Look in "Transfer Amount Details" section (bottom right). Find "{amount_label}" - the destination amount in {unit} (e.g., {unit}10,000.00). Return the numeric value only, no "{unit}" or commas (e.g., 10000.00). Use 0.00 if not found.',
    ]
    if additional_label:
        lines.extend([
            "",
            f'3. **{additional_label}** - In the same "Transfer Amount Details" section, find "{additional_label}" (e.g., {unit}250.00). Return the numeric value only (e.g., 250.00). Use 0.00 if not found.',
        ])
    json_fields = f'"Date": "...", "{amount_label}": "0.00"'
    if additional_label:
        json_fields += f', "{additional_label}": "0.00"'
    lines.extend([
        "",
        f"Return JSON in this exact format:",
        "{" + json_fields + "}",
    ])
    return "\n".join(lines)


def image_to_base64(pil_image) -> str:
    """Convert PIL Image to base64 string for OpenAI API."""
    buffer = io.BytesIO()
    pil_image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def extract_with_openai(client: OpenAI, image_base64: str, config: dict) -> dict:
    """Use OpenAI Vision API to extract receipt fields from image."""
    prompt = build_extraction_prompt(config)
    amount_label = config["amount_label"]
    additional_label = config.get("additional_amount_label")

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                    },
                ],
            }
        ],
        max_tokens=300,
    )
    text = response.choices[0].message.content.strip()

    # Parse JSON (handle markdown code blocks if present)
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    data = json.loads(text)
    amount = float(data.get(amount_label, 0) or 0)
    additional = float(data.get(additional_label, 0) or 0) if additional_label else 0
    total = amount + additional

    result = {
        "Date": data.get("Date", "N/A"),
        amount_label: f"{amount:.2f}",
        "Total": f"{total:.2f}",
    }
    if additional_label:
        result[additional_label] = f"{additional:.2f}"
    return result


def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: Set OPENAI_API_KEY before running.")
        print("  Option 1: export OPENAI_API_KEY='your-api-key'")
        print("  Option 2: Create a .env file with: OPENAI_API_KEY=your-api-key")
        return

    client = OpenAI(api_key=api_key)
    config = load_config()
    all_data = []

    pdf_files = list(INPUT_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {INPUT_DIR}")
        return

    for pdf_path in pdf_files:
        print(f"Processing: {pdf_path.name}...")

        try:
            pages = convert_from_path(pdf_path)

            for page_num, page in enumerate(pages):
                img_base64 = image_to_base64(page)
                extracted = extract_with_openai(client, img_base64, config)
                extracted["Filename"] = pdf_path.name if len(pages) == 1 else f"{pdf_path.name} (page {page_num+1})"
                all_data.append(extracted)

        except Exception as e:
            print(f"Error processing {pdf_path.name}: {e}")

    df = pd.DataFrame(all_data)
    df["_sort_date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.sort_values("_sort_date", ascending=False).drop(columns=["_sort_date"])
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"\nSuccess! Data saved to {OUTPUT_FILE}")
    total_sum = pd.to_numeric(df["Total"], errors="coerce").sum()
    print(f"Receipts processed: {len(df)}")
    print(f"Sum of amounts: {total_sum:,.2f}")


if __name__ == "__main__":
    main()
