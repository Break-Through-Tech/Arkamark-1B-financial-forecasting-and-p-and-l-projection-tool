import pandas as pd
import numpy as np

# Load Corporación Favorita data
print("Loading Favorita sales data...")
df_favorita = pd.read_csv('data/raw/train.csv')

print(f"\n{'='*50}")
print("CORPORACIÓN FAVORITA SALES DATA")
print(f"{'='*50}")
print(f"Shape: {df_favorita.shape}")
print(f"\nColumns: {df_favorita.columns.tolist()}")
print(f"\nData types:\n{df_favorita.dtypes}")
print(f"\nMissing values:\n{df_favorita.isnull().sum()}")
print(f"\nFirst 5 rows:")
print(df_favorita.head())
print(f"\nSummary statistics:")
print(df_favorita.describe())

# Load Financial data
print(f"\n{'='*50}")
print("FINANCIAL DATA")
print(f"{'='*50}")

try:
    # Adjust filename based on what you downloaded
    df_financials = pd.read_csv('data/raw/incomeStatementHistory_annually.csv')
    print(f"Shape: {df_financials.shape}")
    print(f"Columns: {df_financials.columns.tolist()}")
    print(f"Missing values:\n{df_financials.isnull().sum()}")
except FileNotFoundError:
    print("Financial data file not found. Check data/raw/ for the correct filename")