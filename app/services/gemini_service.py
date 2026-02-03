from google import genai
from google.genai import types
from typing import List, Dict, Any, Optional
import json

from app.core.config import settings

SYSTEM_INSTRUCTION = """
You are VanTrack AI, a sleek and ultra-responsive financial co-pilot.
Your goal is to make bookkeeping frictionless and invisible.

### CORE ACCOUNTING LOGIC (STRICT):

1. **Liquidity (cash/bank)**: Your available money.
2. **Receivables (credit)**: Money others owe YOU. (Asset)
3. **Payables (loan)**: Money YOU owe others. (Liability)

### TRANSACTION TYPES:

| Type | Meaning |
|------|---------|
| income | Cash received (regular sale, NOT debt collection) |
| expense | Cash paid out (regular purchase, NOT debt repayment) |
| credit_receivable | Credit SALE - they owe you (no cash yet) |
| credit_payable | Credit PURCHASE - you owe them (no cash yet) |
| loan_receivable | You LENT money - they owe you (cash out) |
| loan_payable | You BORROWED money - you owe them (cash in) |
| payment_received | Someone paid you for an existing debt (reduces receivable) |
| payment_made | You paid someone for an existing debt (reduces payable) |

### MONEY FLOW EXTRACTION RULES:

#### CASH TRANSACTIONS (immediate money movement):
- **CASH INCOME:** User receives cash/bank payment (NOT related to existing debt).
  - Example: "Sold goods for $100 cash"
  - Mapping: type: 'income', account: 'cash' or 'bank', amount: 100.

- **CASH EXPENSE:** User pays with cash/bank (NOT related to existing debt).
  - Example: "Bought supplies for $50 cash"
  - Mapping: type: 'expense', account: 'cash' or 'bank', amount: 50.

#### CREDIT TRANSACTIONS (trade credit - deferred payment):
- **CREDIT SALE (credit_receivable):** User sells on credit, payment deferred.
  - Example: "Sold $200 worth of goods to John on credit"
  - Action: NO cash received yet. Receivable increases.
  - Mapping: type: 'credit_receivable', account: 'cash', amount: 200, contact: 'John'.

- **CREDIT PURCHASE (credit_payable):** User buys on credit, payment deferred.
  - Example: "Bought $150 inventory from Supplier on credit"
  - Action: NO cash paid yet. Payable increases.
  - Mapping: type: 'credit_payable', account: 'cash', amount: 150, contact: 'Supplier'.

#### LOAN TRANSACTIONS (lending/borrowing money):
- **LENDING MONEY (loan_receivable):** You lend money to someone.
  - Example: "Lent $10 to John from cash"
  - Action: Money leaves 'cash', they owe you.
  - Mapping: type: 'loan_receivable', account: 'cash', amount: 10, contact: 'John'.

- **BORROWING MONEY (loan_payable):** You borrow money from someone.
  - Example: "Borrowed $50 from Sarah into bank"
  - Action: Money enters 'bank', you owe them.
  - Mapping: type: 'loan_payable', account: 'bank', amount: 50, contact: 'Sarah'.

#### PAYMENT TRANSACTIONS (settling existing debts):
- **PAYMENT RECEIVED (payment_received):** Someone pays what they owe you.
  - Triggers: "paid back", "paid me", "received payment", "collected", "John paid $50"
  - Example: "John paid $50 of what he owes"
  - Action: Cash in, reduces their debt to you.
  - Mapping: type: 'payment_received', account: 'cash' or 'bank', amount: 50, contact: 'John'.
  - If context has open debts for this contact, set linkedTransactionId to the debt's ID.

- **PAYMENT MADE (payment_made):** You pay what you owe.
  - Triggers: "paid off", "repaid", "paid back to", "settled", "paid $100 to Supplier"
  - Example: "Paid $100 to Supplier for the credit purchase"
  - Action: Cash out, reduces your debt to them.
  - Mapping: type: 'payment_made', account: 'cash' or 'bank', amount: 100, contact: 'Supplier'.
  - If context has open debts for this contact, set linkedTransactionId to the debt's ID.

### LINKING PAYMENTS TO DEBTS:
When the user mentions paying or receiving payment related to an existing debt:
1. Look at the [Open Debts] context provided
2. Match by contact name
3. Set linkedTransactionId to the matching debt's ID
4. If multiple debts exist for same contact, pick the oldest one or ask for clarification

### CRITICAL:
- "on credit" / "credit sale" = credit_receivable (NOT income)
- "on credit" / "credit purchase" = credit_payable (NOT expense)
- "Lent" / "gave loan" = loan_receivable
- "Borrowed" / "took loan" = loan_payable
- "paid back" / "repaid" / "settled" / "collected" = payment_received or payment_made
- Use payment_received/payment_made when settling EXISTING debts
- Use income/expense ONLY for NEW cash transactions unrelated to debts

### LANGUAGE RULES (CRITICAL):
- ALWAYS detect the language the user is writing in
- ALWAYS respond in the SAME language the user used in their message
- If user writes in Thai, respond in Thai
- If user writes in Korean, respond in Korean
- If user writes in any language, respond in that language
- The questionResponse field MUST be in the user's language
- Do NOT default to English unless the user writes in English

### RESPONSE TONE (CRITICAL):
- When you extract transactions, NEVER say "I have recorded" or "I have saved" or "I have added"
- Instead, say you "detected" or "extracted" or "found" the transactions
- Encourage the user to REVIEW and SYNC manually
- Example good responses:
  - "I detected 2 transactions. Please review and tap sync if correct."
  - "Found an expense entry. Feel free to adjust before syncing."
  - "Extracted: Lunch $15. Review and sync when ready."
- The user must manually confirm/sync each draft - you are just extracting, not recording

Always respond in the requested JSON format. Keep conversational text minimal.
"""


async def retry_async(fn, retries=2, delay=1.5):
    import asyncio
    try:
        return await fn()
    except Exception as error:
        error_str = str(error)
        is_quota_error = '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str or 'quota' in error_str.lower()
        
        if retries > 0 and is_quota_error:
            import random
            wait_time = delay + (random.random() * 0.5)
            await asyncio.sleep(wait_time)
            return await retry_async(fn, retries - 1, delay * 2)
        raise error


async def parse_financial_input(
    input_text: str,
    history: Optional[List[Dict[str, Any]]] = None,
    pending_drafts: Optional[List[Dict[str, Any]]] = None,
    open_debts: Optional[List[Dict[str, Any]]] = None,
    currency_code: str = "USD",
    currency_symbol: str = "$",
    language_code: str = "en",
    attachments: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    
    if not settings.GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not configured")
    
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    async def call_api():
        contents = []
        
        # Add recent history (last 3 messages)
        if history:
            recent_history = history[-3:]
            for msg in recent_history:
                role = "user" if msg.get("role") == "user" else "model"
                contents.append(types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg.get("content", ""))]
                ))
        
        # Add pending drafts context
        if pending_drafts and len(pending_drafts) > 0:
            drafts_summary = " ".join([
                f"[type:{d.get('type')} | account:{d.get('account')} | amount:{d.get('amount')} | desc:{d.get('description')}]"
                for d in pending_drafts
            ])
            contents.append(types.Content(
                role="user",
                parts=[types.Part.from_text(text=f"[Context: Pending entries (do not duplicate): {drafts_summary}]")]
            ))
        
        # Add open debts context
        if open_debts and len(open_debts) > 0:
            debts_summary = "; ".join([
                f"[ID:{d.get('id')}] {d.get('contact', 'Unknown')}: ${d.get('remaining_amount', d.get('amount'))} ({d.get('type')})"
                for d in open_debts
            ])
            contents.append(types.Content(
                role="user",
                parts=[types.Part.from_text(text=f"[Open Debts: {debts_summary}]")]
            ))
        
        # Add currency and language context
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=f"[Currency: {currency_code} ({currency_symbol})]")]
        ))
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=f"[Language: {language_code}]")]
        ))
        
        # Build user message parts
        user_parts = []
        
        # Add attachments if any
        if attachments:
            for att in attachments:
                if att.get("type") not in ["image", "audio"]:
                    continue
                data_url = att.get("data_url", "")
                data = data_url.split(",")[1] if "," in data_url else data_url
                if data:
                    user_parts.append(types.Part.from_bytes(
                        data=bytes(data, 'utf-8'),
                        mime_type=att.get("mime_type", "image/png")
                    ))
        
        # Add input text
        trimmed_input = input_text.strip()
        fallback_prompt = "Extract transactions from the attached media." if attachments else trimmed_input
        user_parts.append(types.Part.from_text(text=trimmed_input or fallback_prompt))
        
        contents.append(types.Content(role="user", parts=user_parts))
        
        # Build system instruction
        from datetime import datetime
        now = datetime.now()
        today_iso = now.strftime("%Y-%m-%d")
        today_weekday = now.strftime("%A")  # e.g., "Monday"
        
        currency_instruction = f"\n\nIMPORTANT: The user's currency is {currency_code} ({currency_symbol}). When parsing amounts, assume this currency unless explicitly stated otherwise."
        language_instruction = f"\n\nCRITICAL LANGUAGE RULE: You MUST respond in the SAME language the user writes in. Detect the user's input language and respond ONLY in that language. If user writes in Thai, respond in Thai. If user writes in Korean, respond in Korean. NEVER default to English unless the user writes in English. The questionResponse field MUST match the user's language."
        date_instruction = f"\n\nIMPORTANT: Today is {today_weekday}, {today_iso}. Calculate actual dates from relative references:\n- 'yesterday' = subtract 1 day from today\n- 'last Friday' = find the most recent Friday before today\n- '3 days ago' = subtract 3 days from today\n- 'last week' = subtract 7 days from today\n- 'last month' = same day last month\nAlways output the calculated date in ISO format (YYYY-MM-DD)."
        
        full_instruction = SYSTEM_INSTRUCTION + currency_instruction + language_instruction + date_instruction
        
        response = await client.aio.models.generate_content(
            model="gemini-3-flash-preview",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=full_instruction,
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "description": "CRITICAL: The questionResponse field MUST be written in the SAME language the user used in their input message. Detect user's language and respond in that language.",
                    "properties": {
                        "isQuestion": {"type": "boolean"},
                        "questionResponse": {
                            "type": "string",
                            "description": "Response text in the SAME language as the user's input. If user writes in Thai, respond in Thai. If user writes in Korean, respond in Korean. NEVER default to English."
                        },
                        "isCorrection": {"type": "boolean"},
                        "transactions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "amount": {"type": "number"},
                                    "description": {"type": "string"},
                                    "category": {"type": "string"},
                                    "contact": {"type": "string"},
                                    "date": {
                                        "type": "string",
                                        "description": "Transaction occurring date in ISO format (YYYY-MM-DD). Use today's date if not explicitly mentioned."
                                    },
                                    "dueDate": {"type": "string"},
                                    "type": {
                                        "type": "string",
                                        "enum": ["expense", "income", "transfer", "credit_receivable", "credit_payable", "loan_receivable", "loan_payable", "payment_received", "payment_made"]
                                    },
                                    "account": {
                                        "type": "string",
                                        "enum": ["cash", "bank"]
                                    },
                                    "linkedTransactionId": {"type": "string"}
                                },
                                "required": ["amount", "description", "type", "account", "date"]
                            }
                        }
                    },
                    "required": ["isQuestion"]
                }
            )
        )
        
        text = response.text.strip() if response.text else ""
        if not text:
            raise ValueError("Empty response from AI")
        print("Ai response: ", text)
        
        parsed = json.loads(text)
        print(f"[DEBUG] AI Response: {parsed}")  # Debug log
        return parsed
    
    try:
        result = await retry_async(call_api)
        return {
            "transactions": result.get("transactions", []),
            "is_question": result.get("isQuestion", False),
            "question_response": result.get("questionResponse"),
            "is_correction": result.get("isCorrection")
        }
    except Exception as error:
        error_str = str(error)
        if '429' in error_str or 'quota' in error_str.lower():
            raise ValueError("QUOTA_EXHAUSTED")
        raise error
