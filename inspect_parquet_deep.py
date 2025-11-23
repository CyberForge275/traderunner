import pandas as pd
import numpy as np

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

def inspect_parquet(path):
    print(f"--- Inspecting {path} ---")
    try:
        df = pd.read_parquet(path)
        print(f"Shape: {df.shape}")
        print("\nIndex:")
        print(df.index)
        print(f"Index names: {df.index.names}")
        if isinstance(df.index, pd.MultiIndex):
            print(f"Index levels: {df.index.levels}")
            print(f"Level 0 sample: {df.index.get_level_values(0)[:10]}")
        
        print("\nColumns & Dtypes:")
        print(df.dtypes)
        
        print("\nFirst 5 rows:")
        print(df.head())
        
        print("\nSample of unique values for object/string columns:")
        for col in df.columns:
            if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
                print(f"Column '{col}': {df[col].dropna().unique()[:10]}")
                
        print("\nChecking for hidden/categorical columns:")
        for col in df.columns:
            if isinstance(df[col].dtype, pd.CategoricalDtype):
                print(f"Column '{col}' is categorical. Categories: {df[col].cat.categories[:10]}")

        print("\nChecking 'ts_id' stats:")
        if 'ts_id' in df.columns:
            print(f"Unique ts_id count: {df['ts_id'].nunique()}")
            print(f"Min ts_id: {df['ts_id'].min()}")
            print(f"Max ts_id: {df['ts_id'].max()}")

    except Exception as e:
        print(f"Error reading file: {e}")

if __name__ == "__main__":
    inspect_parquet("data/universe/rudometkin.parquet")
