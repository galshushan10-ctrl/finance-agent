import json
import subprocess
import os
from .base_agent import BaseAgent

class ScraperAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Lior",
            role="סוכן שליפת נתונים בנקאיים",
            system_prompt="""אתה Lior, אחראי על שליפת נתונים פיננסיים מהבנק.
תפקידך: לשלוף נתונים, לנקות אותם ולהעביר אותם מוכנים לניתוח."""
        )
        self.transactions_path = "/Users/galshushan/finance-agent/transactions.json"

    def scrape(self) -> bool:
        result = subprocess.run(
            ["node", "/Users/galshushan/finance-agent/scrape.mjs"],
            capture_output=True, text=True,
            cwd="/Users/galshushan/finance-agent"
        )
        return result.returncode == 0

    def load(self) -> list:
        with open(self.transactions_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        transactions = []
        for account in data["accounts"]:
            for txn in account["txns"]:
                amount = txn.get("chargedAmount", 0)
                if amount < 0:
                    transactions.append({
                        "date": txn.get("date", "")[:10],
                        "amount": abs(amount),
                        "description": txn.get("description", ""),
                        "memo": txn.get("memo", ""),
                    })
        return transactions
