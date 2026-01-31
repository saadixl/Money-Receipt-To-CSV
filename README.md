# Money Receipt to CSV

Extract date and amounts from money transfer receipt PDFs using OpenAI Vision and save the data to a CSV file.

## Setup

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

   On macOS, `pdf2image` also needs [Poppler](https://poppler.freedesktop.org/):

   ```bash
   brew install poppler
   ```

2. **Configure**

   Copy `.env.example` to `.env` and set your OpenAI API key:

   ```bash
   cp .env.example .env
   ```

   Required:

   - `OPENAI_API_KEY` – your OpenAI API key

   Optional (receipt format):

   - `MONEY_UNIT` – currency symbol (default: CCY)
   - `SENDER_NAME` – sender description for the prompt (default: a sender)
   - `AMOUNT_LABEL` – label for the main amount on the receipt (default: Amount)
   - `ADDITIONAL_AMOUNT_LABEL` – label for the extra amount (default: Additional Amount). Leave empty to skip.

## Usage

1. Put receipt PDFs in the `receipts/` folder.
2. Run:

   ```bash
   python main.py
   ```

3. Output is written to `receipt_data.csv` (date, amounts, total, filename), sorted by date.

## Output

See `receipt_data_example.csv` for an example of the generated CSV.
