# datastructure_analyzer

Analyses the identifier and relationship structure of a key-value store 
aggregating data from multiple upstream systems.

## Setup
```bash
pip install pandas matplotlib openpyxl duckdb anthropic python-dotenv
```

## Usage
Drop your input file as `input/excel.xlsx` and run:
```bash
python run.py
```

## Environment
Copy `.env.example` to `.env` and add your `ANTHROPIC_API_KEY` for 
LLM-generated narrative. The analysis runs without it using a structured fallback.