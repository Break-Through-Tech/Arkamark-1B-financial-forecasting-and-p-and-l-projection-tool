import pandas as pd
import numpy as np


def load_favorita():
    print(f"\n{'='*50}")
    print("CORPORACIÓN FAVORITA SALES DATA")
    print(f"{'='*50}")

    try:
        df = pd.read_csv('data/raw/train.csv')
        print(f"Shape: {df.shape}")
        print(f"\nColumns: {df.columns.tolist()}")
        print(f"\nData types:\n{df.dtypes}")
        print(f"\nMissing values:\n{df.isnull().sum()}")
        print(f"\nFirst 5 rows:")
        print(df.head())
        print(f"\nSummary statistics:")
        print(df.describe())
        return df
    except FileNotFoundError:
        print("Sales data file not found. Check data/raw/ for the correct filename")
        return None


def load_financials():
    print(f"\n{'='*50}")
    print("FINANCIAL DATA")
    print(f"{'='*50}")

    try:
        df = pd.read_csv('data/raw/incomeStatementHistory_annually.csv')
        print(f"Shape: {df.shape}")
        print(f"Columns: {df.columns.tolist()}")
        print(f"\nData types:\n{df.dtypes}")
        print(f"\nMissing values:\n{df.isnull().sum()}")
        print(f"\nFirst 5 rows:")
        print(df.head())
        print(f"\nSummary statistics:")
        print(df.describe())
        return df
    except FileNotFoundError:
        print("Financial data file not found. Check data/raw/ for the correct filename")
        return None


if __name__ == "__main__":
    df_favorita = load_favorita()
    df_financials = load_financials()

    print(f"\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    if df_favorita is not None:
        print(f"Favorita: {df_favorita.shape[0]} rows, {df_favorita.shape[1]} columns.")
    if df_financials is not None:
        print(f"Financials: {df_financials.shape[0]} rows, {df_financials.shape[1]} columns.")