from pathlib import Path
from typing import List
import pandas as pd
import pdfplumber


def read_excel(filepath: Path) -> pd.DataFrame:
    df = pd.concat(pd.read_excel(filepath, sheet_name=None), ignore_index=True)
    df.columns = [c.strip() for c in df.columns]
    return df


def read_pdf(filepath: Path) -> List[str]:
    pages: List[str] = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            txt = page.extract_text() or ""
            pages.append(txt.strip())
    return pages