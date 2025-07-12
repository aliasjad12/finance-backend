import pandas as pd

# Load your dataset with encoding that handles special characters
df = pd.read_csv("expenses_dataset.csv", encoding="ISO-8859-1")

# Capitalize each category (first letter uppercase, rest lowercase)
df["Category"] = df["Category"].str.strip().str.capitalize()

# Save the cleaned file
df.to_csv("expenses_dataset_cleaned.csv", index=False)
print("Cleaned file saved as 'expenses_dataset_cleaned.csv'")
