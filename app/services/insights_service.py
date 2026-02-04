from google import genai
from google.genai import types
from typing import List, Dict, Any, Optional
import json
from datetime import datetime, timedelta

from app.core.config import settings


INSIGHTS_SYSTEM_INSTRUCTION = """
You are VanTrack AI, a friendly and insightful financial advisor.
Your job is to analyze the user's financial data and provide valuable, actionable insights.

### YOUR PERSONALITY:
- Warm, encouraging, but honest
- Use simple language, avoid jargon
- Be specific with numbers and dates
- Celebrate wins, gently point out areas for improvement
- Keep responses concise but meaningful

### RESPONSE LANGUAGE:
CRITICAL: Respond in the SAME language as specified in the user's language_code.
- If language_code is "th", respond entirely in Thai
- If language_code is "en", respond in English
- If language_code is "ko", respond in Korean
- Match the user's language exactly

### INSIGHT TYPES TO PROVIDE:
1. **Spending Patterns**: Where is money going? Any unusual spikes?
2. **Income Trends**: Is income stable? Growing?
3. **Debt Health**: How are receivables/payables looking?
4. **Cash Flow**: Is more money coming in or going out?
5. **Actionable Tips**: Specific, practical suggestions

### FORMATTING:
- Use bullet points for clarity
- Include specific amounts and percentages
- Reference specific transactions when relevant
- Keep total response under 300 words
"""


QUESTION_SYSTEM_INSTRUCTION = """
You are VanTrack AI, a helpful financial assistant.
The user will ask questions about their financial data. Answer accurately based on the provided transaction data.

### YOUR PERSONALITY:
- Helpful and direct
- Always cite specific numbers from the data
- If data is insufficient, say so honestly
- Suggest follow-up questions if relevant

### RESPONSE LANGUAGE:
CRITICAL: Respond in the SAME language as the user's question.
Detect the language of the question and respond in that same language.

### CAPABILITIES:
- Calculate totals, averages, comparisons
- Find specific transactions
- Analyze trends over time
- Compare categories, contacts, time periods
- Answer "how much", "when", "who", "what" questions

### FORMATTING:
- Be concise but complete
- Use numbers and dates
- Format currency amounts clearly
"""


async def generate_weekly_summary(
    transactions: List[Dict[str, Any]],
    currency_symbol: str = "$",
    language_code: str = "en"
) -> str:
    """Generate AI-powered weekly financial summary."""
    
    if not settings.GEMINI_API_KEY:
        return "AI insights unavailable. Please configure GEMINI_API_KEY."
    
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    # Prepare transaction data for AI
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Filter transactions
    this_week = []
    last_month = []
    
    for tx in transactions:
        tx_date = tx.get('date')
        if isinstance(tx_date, str):
            try:
                tx_date = datetime.fromisoformat(tx_date.replace('Z', '+00:00'))
            except:
                continue
        elif not isinstance(tx_date, datetime):
            continue
            
        if tx_date >= week_ago:
            this_week.append(tx)
        if tx_date >= month_ago:
            last_month.append(tx)
    
    # Build context
    context = f"""
## Financial Data Summary

### This Week's Transactions ({len(this_week)} total):
"""
    
    # Categorize this week
    week_income = sum(tx['amount'] for tx in this_week if tx.get('type') == 'income')
    week_expense = sum(tx['amount'] for tx in this_week if tx.get('type') == 'expense')
    week_received = sum(tx['amount'] for tx in this_week if tx.get('type') == 'payment_received')
    week_paid = sum(tx['amount'] for tx in this_week if tx.get('type') == 'payment_made')
    
    context += f"""
- Total Income: {currency_symbol}{week_income:,.2f}
- Total Expenses: {currency_symbol}{week_expense:,.2f}
- Payments Received (debt collection): {currency_symbol}{week_received:,.2f}
- Payments Made (debt repayment): {currency_symbol}{week_paid:,.2f}
- Net Cash Flow: {currency_symbol}{(week_income + week_received - week_expense - week_paid):,.2f}

### Expense Breakdown This Week:
"""
    
    # Group expenses by category
    expense_by_category = {}
    for tx in this_week:
        if tx.get('type') == 'expense':
            cat = tx.get('category') or 'Uncategorized'
            expense_by_category[cat] = expense_by_category.get(cat, 0) + tx['amount']
    
    for cat, amount in sorted(expense_by_category.items(), key=lambda x: -x[1])[:5]:
        context += f"- {cat}: {currency_symbol}{amount:,.2f}\n"
    
    # Add monthly comparison
    month_income = sum(tx['amount'] for tx in last_month if tx.get('type') == 'income')
    month_expense = sum(tx['amount'] for tx in last_month if tx.get('type') == 'expense')
    
    context += f"""
### Last 30 Days Overview:
- Total Income: {currency_symbol}{month_income:,.2f}
- Total Expenses: {currency_symbol}{month_expense:,.2f}
- Savings Rate: {((month_income - month_expense) / month_income * 100) if month_income > 0 else 0:.1f}%

### Open Debts:
"""
    
    # Calculate open debts
    receivables = sum(tx['amount'] - (tx.get('remaining_amount') or tx['amount']) 
                     for tx in transactions 
                     if tx.get('type') in ['credit_receivable', 'loan_receivable'] 
                     and tx.get('status') != 'settled')
    payables = sum(tx['amount'] - (tx.get('remaining_amount') or tx['amount'])
                  for tx in transactions 
                  if tx.get('type') in ['credit_payable', 'loan_payable']
                  and tx.get('status') != 'settled')
    
    # Recalculate properly - remaining amount is what's still owed
    total_receivable = sum(tx.get('remaining_amount', tx['amount'])
                          for tx in transactions 
                          if tx.get('type') in ['credit_receivable', 'loan_receivable'] 
                          and tx.get('status') != 'settled')
    total_payable = sum(tx.get('remaining_amount', tx['amount'])
                       for tx in transactions 
                       if tx.get('type') in ['credit_payable', 'loan_payable']
                       and tx.get('status') != 'settled')
    
    context += f"""
- Others owe you: {currency_symbol}{total_receivable:,.2f}
- You owe others: {currency_symbol}{total_payable:,.2f}

### Recent Transactions (last 5):
"""
    
    for tx in sorted(this_week, key=lambda x: x.get('date', ''), reverse=True)[:5]:
        context += f"- {tx.get('description', 'No description')}: {currency_symbol}{tx['amount']:,.2f} ({tx.get('type', 'unknown')})\n"
    
    context += f"""
### User's Language: {language_code}
### Currency: {currency_symbol}
### Today's Date: {today.strftime('%Y-%m-%d')}

Please provide a friendly, insightful weekly summary based on this data.
Focus on: key observations, spending patterns, and 1-2 actionable tips.
"""
    
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=context)])],
            config=types.GenerateContentConfig(
                system_instruction=INSIGHTS_SYSTEM_INSTRUCTION,
                temperature=0.7,
                max_output_tokens=500
            )
        )
        
        return response.text.strip() if response.text else "Unable to generate insights at this time."
        
    except Exception as e:
        print(f"[ERROR] Insights generation failed: {e}")
        return f"Unable to generate insights: {str(e)}"


async def answer_financial_question(
    question: str,
    transactions: List[Dict[str, Any]],
    contacts: List[Dict[str, Any]],
    currency_symbol: str = "$",
    language_code: str = "en"
) -> str:
    """Answer user's question about their financial data."""
    
    if not settings.GEMINI_API_KEY:
        return "AI unavailable. Please configure GEMINI_API_KEY."
    
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    today = datetime.now()
    
    # Build comprehensive data context
    context = f"""
## User's Financial Data

### All Transactions ({len(transactions)} total):
"""
    
    # Group by type
    by_type = {}
    for tx in transactions:
        t = tx.get('type', 'unknown')
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(tx)
    
    for tx_type, txs in by_type.items():
        total = sum(tx['amount'] for tx in txs)
        context += f"\n**{tx_type}** ({len(txs)} transactions, total: {currency_symbol}{total:,.2f}):\n"
        for tx in sorted(txs, key=lambda x: x.get('date', ''), reverse=True)[:10]:
            date_str = tx.get('date', 'unknown date')
            if isinstance(date_str, datetime):
                date_str = date_str.strftime('%Y-%m-%d')
            elif isinstance(date_str, str) and 'T' in date_str:
                date_str = date_str.split('T')[0]
            context += f"  - {date_str}: {tx.get('description', 'No desc')} - {currency_symbol}{tx['amount']:,.2f}"
            if tx.get('contact_name'):
                context += f" (contact: {tx['contact_name']})"
            if tx.get('category'):
                context += f" [{tx['category']}]"
            context += "\n"
    
    # Add contacts
    if contacts:
        context += f"\n### Contacts ({len(contacts)}):\n"
        for c in contacts[:20]:
            context += f"- {c.get('name', 'Unknown')}\n"
    
    # Add summary stats
    total_income = sum(tx['amount'] for tx in transactions if tx.get('type') == 'income')
    total_expense = sum(tx['amount'] for tx in transactions if tx.get('type') == 'expense')
    
    context += f"""
### Summary Statistics:
- Total Income (all time): {currency_symbol}{total_income:,.2f}
- Total Expenses (all time): {currency_symbol}{total_expense:,.2f}
- Net: {currency_symbol}{(total_income - total_expense):,.2f}

### Today's Date: {today.strftime('%Y-%m-%d')}
### Currency: {currency_symbol}

## User's Question:
{question}

Please answer the question based on the data above. Be specific with numbers and dates.
"""
    
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=context)])],
            config=types.GenerateContentConfig(
                system_instruction=QUESTION_SYSTEM_INSTRUCTION,
                temperature=0.3,
                max_output_tokens=400
            )
        )
        
        return response.text.strip() if response.text else "I couldn't find an answer to that question."
        
    except Exception as e:
        print(f"[ERROR] Question answering failed: {e}")
        return f"Unable to answer: {str(e)}"


HEALTH_SCORE_INSTRUCTION = """
You are VanTrack AI, a friendly financial health advisor.
Based on the user's Financial Health Score breakdown, provide 2-3 specific, actionable tips to improve their score.

### YOUR PERSONALITY:
- Encouraging but honest
- Focus on the LOWEST scoring areas first
- Give specific, actionable advice (not generic)
- Keep it brief - max 3 bullet points

### RESPONSE LANGUAGE:
CRITICAL: Respond in the SAME language as specified in the user's language_code.

### FORMAT:
- Use bullet points
- Each tip should be 1-2 sentences max
- Focus on quick wins they can do this week
"""


def calculate_health_score(
    transactions: List[Dict[str, Any]],
    currency_symbol: str = "$"
) -> Dict[str, Any]:
    """Calculate financial health score (0-100) based on multiple factors."""
    
    today = datetime.now()
    month_ago = today - timedelta(days=30)
    three_months_ago = today - timedelta(days=90)
    
    # Parse dates and filter transactions
    def parse_date(tx):
        tx_date = tx.get('date')
        if isinstance(tx_date, str):
            try:
                return datetime.fromisoformat(tx_date.replace('Z', '+00:00').replace('+00:00', ''))
            except:
                return None
        return tx_date if isinstance(tx_date, datetime) else None
    
    all_txs = [(tx, parse_date(tx)) for tx in transactions]
    all_txs = [(tx, d) for tx, d in all_txs if d is not None]
    
    last_month = [(tx, d) for tx, d in all_txs if d >= month_ago]
    last_3_months = [(tx, d) for tx, d in all_txs if d >= three_months_ago]
    
    # 1. SAVINGS RATE (0-30 points)
    # (Income - Expenses) / Income * 100
    month_income = sum(tx['amount'] for tx, d in last_month if tx.get('type') == 'income')
    month_expense = sum(tx['amount'] for tx, d in last_month if tx.get('type') == 'expense')
    
    if month_income > 0:
        savings_rate = (month_income - month_expense) / month_income
        savings_score = min(30, max(0, savings_rate * 100))  # 30% savings = full points
    else:
        savings_rate = 0
        savings_score = 0
    
    # 2. DEBT-TO-INCOME RATIO (0-25 points)
    # Lower is better: <20% = excellent, >50% = poor
    total_payable = sum(
        tx.get('remaining_amount', tx['amount'])
        for tx in transactions
        if tx.get('type') in ['credit_payable', 'loan_payable']
        and tx.get('status') != 'settled'
    )
    total_receivable = sum(
        tx.get('remaining_amount', tx['amount'])
        for tx in transactions
        if tx.get('type') in ['credit_receivable', 'loan_receivable']
        and tx.get('status') != 'settled'
    )
    
    avg_monthly_income = month_income if month_income > 0 else 1
    debt_ratio = total_payable / avg_monthly_income if avg_monthly_income > 0 else 0
    
    if debt_ratio <= 0.2:
        debt_score = 25
    elif debt_ratio <= 0.5:
        debt_score = 25 - ((debt_ratio - 0.2) / 0.3) * 15
    else:
        debt_score = max(0, 10 - (debt_ratio - 0.5) * 10)
    
    # 3. SPENDING CONSISTENCY (0-25 points)
    # Compare weekly spending variance - lower variance = more consistent
    weeks_spending = {}
    for tx, d in last_month:
        if tx.get('type') == 'expense':
            week_num = d.isocalendar()[1]
            weeks_spending[week_num] = weeks_spending.get(week_num, 0) + tx['amount']
    
    if len(weeks_spending) >= 2:
        avg_weekly = sum(weeks_spending.values()) / len(weeks_spending)
        if avg_weekly > 0:
            variance = sum((v - avg_weekly) ** 2 for v in weeks_spending.values()) / len(weeks_spending)
            std_dev = variance ** 0.5
            cv = std_dev / avg_weekly  # Coefficient of variation
            consistency_score = max(0, 25 - cv * 25)  # Lower CV = higher score
        else:
            consistency_score = 25
    else:
        consistency_score = 15  # Not enough data, give average score
    
    # 4. EMERGENCY FUND STATUS (0-20 points)
    # Based on net position (receivables - payables) relative to monthly expenses
    net_position = total_receivable - total_payable
    monthly_expenses = month_expense if month_expense > 0 else 1
    
    months_covered = net_position / monthly_expenses if monthly_expenses > 0 else 0
    
    if months_covered >= 3:
        emergency_score = 20
    elif months_covered >= 1:
        emergency_score = 10 + (months_covered - 1) * 5
    elif months_covered >= 0:
        emergency_score = months_covered * 10
    else:
        emergency_score = max(0, 5 + months_covered * 5)  # Negative = in debt
    
    # TOTAL SCORE
    total_score = int(savings_score + debt_score + consistency_score + emergency_score)
    total_score = min(100, max(0, total_score))
    
    # Determine grade
    if total_score >= 80:
        grade = "Excellent"
        grade_color = "green"
    elif total_score >= 60:
        grade = "Good"
        grade_color = "blue"
    elif total_score >= 40:
        grade = "Fair"
        grade_color = "yellow"
    else:
        grade = "Needs Work"
        grade_color = "red"
    
    return {
        "score": total_score,
        "grade": grade,
        "grade_color": grade_color,
        "breakdown": {
            "savings_rate": {
                "score": round(savings_score, 1),
                "max": 30,
                "value": f"{savings_rate * 100:.1f}%",
                "label": "Savings Rate"
            },
            "debt_ratio": {
                "score": round(debt_score, 1),
                "max": 25,
                "value": f"{debt_ratio * 100:.1f}%",
                "label": "Debt-to-Income"
            },
            "consistency": {
                "score": round(consistency_score, 1),
                "max": 25,
                "value": f"{len(weeks_spending)} weeks tracked",
                "label": "Spending Consistency"
            },
            "emergency_fund": {
                "score": round(emergency_score, 1),
                "max": 20,
                "value": f"{months_covered:.1f} months",
                "label": "Emergency Buffer"
            }
        },
        "summary": {
            "monthly_income": month_income,
            "monthly_expense": month_expense,
            "total_receivable": total_receivable,
            "total_payable": total_payable,
            "net_position": net_position
        }
    }


async def generate_health_tips(
    health_data: Dict[str, Any],
    currency_symbol: str = "$",
    language_code: str = "en"
) -> str:
    """Generate AI tips to improve financial health score."""
    
    if not settings.GEMINI_API_KEY:
        return "AI tips unavailable. Please configure GEMINI_API_KEY."
    
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    breakdown = health_data['breakdown']
    summary = health_data['summary']
    
    # Find lowest scoring areas
    scores = [
        (breakdown['savings_rate']['label'], breakdown['savings_rate']['score'], breakdown['savings_rate']['max'], breakdown['savings_rate']['value']),
        (breakdown['debt_ratio']['label'], breakdown['debt_ratio']['score'], breakdown['debt_ratio']['max'], breakdown['debt_ratio']['value']),
        (breakdown['consistency']['label'], breakdown['consistency']['score'], breakdown['consistency']['max'], breakdown['consistency']['value']),
        (breakdown['emergency_fund']['label'], breakdown['emergency_fund']['score'], breakdown['emergency_fund']['max'], breakdown['emergency_fund']['value']),
    ]
    scores.sort(key=lambda x: x[1] / x[2])  # Sort by percentage of max
    
    context = f"""
## Financial Health Score: {health_data['score']}/100 ({health_data['grade']})

### Score Breakdown (sorted by priority - lowest first):
"""
    for label, score, max_score, value in scores:
        pct = (score / max_score) * 100
        context += f"- {label}: {score:.1f}/{max_score} ({pct:.0f}%) - Current: {value}\n"
    
    context += f"""
### Financial Summary:
- Monthly Income: {currency_symbol}{summary['monthly_income']:,.2f}
- Monthly Expenses: {currency_symbol}{summary['monthly_expense']:,.2f}
- Others Owe You: {currency_symbol}{summary['total_receivable']:,.2f}
- You Owe Others: {currency_symbol}{summary['total_payable']:,.2f}

### Language: {language_code}

Please provide 2-3 specific tips to improve the score, focusing on the lowest-scoring areas.
"""
    
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=context)])],
            config=types.GenerateContentConfig(
                system_instruction=HEALTH_SCORE_INSTRUCTION,
                temperature=0.5,
                max_output_tokens=300
            )
        )
        
        return response.text.strip() if response.text else "Keep tracking your finances to get personalized tips!"
        
    except Exception as e:
        print(f"[ERROR] Health tips generation failed: {e}")
        return "Keep tracking your finances to get personalized tips!"


# Benchmark averages (based on typical spending patterns)
# These could be replaced with real aggregate data in the future
SPENDING_BENCHMARKS = {
    "food": 0.15,           # 15% of income
    "dining": 0.05,         # 5% of income
    "transport": 0.10,      # 10% of income
    "entertainment": 0.05,  # 5% of income
    "shopping": 0.10,       # 10% of income
    "utilities": 0.08,      # 8% of income
    "health": 0.05,         # 5% of income
    "education": 0.05,      # 5% of income
    "savings_rate": 0.20,   # 20% savings rate
    "debt_ratio": 0.30,     # 30% debt-to-income
}


def calculate_spending_comparisons(
    transactions: List[Dict[str, Any]],
    currency_symbol: str = "$"
) -> Dict[str, Any]:
    """Compare user's spending to anonymous benchmarks."""
    
    today = datetime.now()
    month_ago = today - timedelta(days=30)
    
    # Parse dates and filter to last month
    def parse_date(tx):
        tx_date = tx.get('date')
        if isinstance(tx_date, str):
            try:
                return datetime.fromisoformat(tx_date.replace('Z', '+00:00').replace('+00:00', ''))
            except:
                return None
        return tx_date if isinstance(tx_date, datetime) else None
    
    last_month_txs = [
        tx for tx in transactions
        if (d := parse_date(tx)) and d >= month_ago
    ]
    
    # Calculate monthly income and expenses
    monthly_income = sum(
        tx['amount'] for tx in last_month_txs 
        if tx.get('type') == 'income'
    )
    monthly_expenses = sum(
        tx['amount'] for tx in last_month_txs 
        if tx.get('type') == 'expense'
    )
    
    # Group expenses by category
    category_spending: Dict[str, float] = {}
    for tx in last_month_txs:
        if tx.get('type') == 'expense':
            category = (tx.get('category') or 'other').lower()
            category_spending[category] = category_spending.get(category, 0) + tx['amount']
    
    # Calculate comparisons
    comparisons = []
    
    if monthly_income > 0:
        # Savings rate comparison
        actual_savings_rate = (monthly_income - monthly_expenses) / monthly_income
        benchmark_savings = SPENDING_BENCHMARKS['savings_rate']
        diff_pct = ((actual_savings_rate - benchmark_savings) / benchmark_savings) * 100
        
        comparisons.append({
            "category": "Savings Rate",
            "your_value": f"{actual_savings_rate * 100:.1f}%",
            "benchmark": f"{benchmark_savings * 100:.0f}%",
            "difference": diff_pct,
            "is_better": actual_savings_rate >= benchmark_savings,
            "insight": f"You save {abs(diff_pct):.0f}% {'more' if diff_pct > 0 else 'less'} than average"
        })
        
        # Category comparisons
        for category, benchmark_pct in SPENDING_BENCHMARKS.items():
            if category in ['savings_rate', 'debt_ratio']:
                continue
                
            # Find matching categories (fuzzy match)
            actual_spending = 0
            for cat, amount in category_spending.items():
                if category in cat or cat in category:
                    actual_spending += amount
            
            if actual_spending > 0 or category in ['food', 'entertainment', 'transport']:
                actual_pct = actual_spending / monthly_income if monthly_income > 0 else 0
                diff_pct = ((actual_pct - benchmark_pct) / benchmark_pct) * 100 if benchmark_pct > 0 else 0
                
                comparisons.append({
                    "category": category.title(),
                    "your_value": f"{currency_symbol}{actual_spending:,.0f}",
                    "your_pct": f"{actual_pct * 100:.1f}%",
                    "benchmark": f"{benchmark_pct * 100:.0f}%",
                    "difference": diff_pct,
                    "is_better": actual_pct <= benchmark_pct,  # Lower spending is better
                    "insight": f"You spend {abs(diff_pct):.0f}% {'less' if diff_pct < 0 else 'more'} than average on {category}"
                })
    
    # Sort by absolute difference (most significant first)
    comparisons.sort(key=lambda x: abs(x['difference']), reverse=True)
    
    # Calculate overall ranking (simplified)
    better_count = sum(1 for c in comparisons if c['is_better'])
    total_count = len(comparisons) if comparisons else 1
    percentile = int((better_count / total_count) * 100)
    
    return {
        "monthly_income": monthly_income,
        "monthly_expenses": monthly_expenses,
        "comparisons": comparisons[:6],  # Top 6 most significant
        "percentile": percentile,
        "summary": f"You're doing better than average in {better_count} of {total_count} categories"
    }


def calculate_smart_predictions(
    transactions: List[Dict[str, Any]],
    currency_symbol: str = "$"
) -> Dict[str, Any]:
    """
    Calculate smart predictions including:
    1. Cash flow forecast for end of month
    2. Bill reminders based on recurring patterns
    3. Debt payoff timeline
    """
    now = datetime.utcnow()
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    days_in_month = 30  # Simplified
    days_passed = now.day
    days_remaining = days_in_month - days_passed
    
    # Analyze last 90 days for patterns
    ninety_days_ago = now - timedelta(days=90)
    recent_transactions = [
        t for t in transactions
        if datetime.fromisoformat(t['date'].replace('Z', '+00:00').replace('+00:00', '')) >= ninety_days_ago
    ]
    
    # Current month transactions
    current_month_txs = [
        t for t in transactions
        if datetime.fromisoformat(t['date'].replace('Z', '+00:00').replace('+00:00', '')) >= current_month_start
    ]
    
    # === 1. CASH FLOW FORECAST ===
    # Calculate average daily income and expenses from last 90 days
    total_income_90d = sum(t['amount'] for t in recent_transactions if t['type'] == 'income')
    total_expenses_90d = sum(t['amount'] for t in recent_transactions if t['type'] == 'expense')
    
    avg_daily_income = total_income_90d / 90 if recent_transactions else 0
    avg_daily_expenses = total_expenses_90d / 90 if recent_transactions else 0
    
    # Current month actuals
    current_income = sum(t['amount'] for t in current_month_txs if t['type'] == 'income')
    current_expenses = sum(t['amount'] for t in current_month_txs if t['type'] == 'expense')
    current_balance = current_income - current_expenses
    
    # Projected end of month
    projected_income = current_income + (avg_daily_income * days_remaining)
    projected_expenses = current_expenses + (avg_daily_expenses * days_remaining)
    projected_balance = projected_income - projected_expenses
    
    cash_flow_forecast = {
        "current_balance": round(current_balance, 2),
        "projected_end_of_month": round(projected_balance, 2),
        "projected_income": round(projected_income, 2),
        "projected_expenses": round(projected_expenses, 2),
        "days_remaining": days_remaining,
        "trend": "positive" if projected_balance > current_balance else "negative",
        "message": f"Based on your patterns, you'll have ~{currency_symbol}{abs(projected_balance):,.0f} by end of month."
    }
    
    # === 2. BILL REMINDERS ===
    # Find recurring expenses by analyzing description patterns and dates
    expense_patterns = {}
    for t in recent_transactions:
        if t['type'] == 'expense':
            desc_lower = t['description'].lower()
            tx_date = datetime.fromisoformat(t['date'].replace('Z', '+00:00').replace('+00:00', ''))
            day_of_month = tx_date.day
            
            # Group by similar descriptions
            key = None
            for keyword in ['rent', 'mortgage', 'electric', 'water', 'internet', 'phone', 'insurance', 
                           'subscription', 'netflix', 'spotify', 'gym', 'loan', 'car payment']:
                if keyword in desc_lower:
                    key = keyword
                    break
            
            if not key:
                # Use first two words as key
                words = desc_lower.split()[:2]
                key = ' '.join(words) if words else desc_lower[:20]
            
            if key not in expense_patterns:
                expense_patterns[key] = {'amounts': [], 'days': [], 'descriptions': []}
            
            expense_patterns[key]['amounts'].append(t['amount'])
            expense_patterns[key]['days'].append(day_of_month)
            expense_patterns[key]['descriptions'].append(t['description'])
    
    # Find recurring bills (appeared 2+ times with similar amounts)
    bill_reminders = []
    for key, data in expense_patterns.items():
        if len(data['amounts']) >= 2:
            avg_amount = sum(data['amounts']) / len(data['amounts'])
            # Check if amounts are consistent (within 20% of average)
            is_consistent = all(abs(a - avg_amount) / avg_amount < 0.2 for a in data['amounts']) if avg_amount > 0 else False
            
            if is_consistent:
                avg_day = round(sum(data['days']) / len(data['days']))
                
                # Check if due soon (within next 7 days)
                days_until_due = avg_day - now.day
                if days_until_due < 0:
                    days_until_due += 30  # Next month
                
                is_upcoming = days_until_due <= 7
                
                bill_reminders.append({
                    "name": key.title(),
                    "amount": round(avg_amount, 2),
                    "usual_day": avg_day,
                    "days_until_due": days_until_due,
                    "is_upcoming": is_upcoming,
                    "message": f"{key.title()} (~{currency_symbol}{avg_amount:,.0f}) is usually due around the {avg_day}{'st' if avg_day == 1 else 'nd' if avg_day == 2 else 'rd' if avg_day == 3 else 'th'}."
                })
    
    # Sort by days until due
    bill_reminders.sort(key=lambda x: x['days_until_due'])
    
    # === 3. DEBT PAYOFF TIMELINE ===
    # Find all outstanding debts
    debts = []
    for t in transactions:
        if t['type'] in ['credit_payable', 'loan_payable']:
            remaining = t.get('remaining_amount', t['amount'])
            if remaining > 0 and t.get('status') != 'settled':
                debts.append({
                    'id': t['id'],
                    'description': t['description'],
                    'contact': t.get('contact_name', 'Unknown'),
                    'original_amount': t['amount'],
                    'remaining': remaining,
                    'due_date': t.get('due_date')
                })
    
    total_debt = sum(d['remaining'] for d in debts)
    
    # Calculate average monthly payment towards debt (from payment_made transactions)
    payments_90d = sum(
        t['amount'] for t in recent_transactions 
        if t['type'] == 'payment_made'
    )
    avg_monthly_payment = (payments_90d / 3) if payments_90d > 0 else 0
    
    # If no payment history, suggest 10% of income
    if avg_monthly_payment == 0 and avg_daily_income > 0:
        avg_monthly_payment = avg_daily_income * 30 * 0.1
    
    # Calculate payoff timeline
    debt_payoff = {
        "total_debt": round(total_debt, 2),
        "debt_count": len(debts),
        "debts": debts[:5],  # Top 5 debts
        "avg_monthly_payment": round(avg_monthly_payment, 2),
        "months_to_payoff": None,
        "payoff_date": None,
        "message": None
    }
    
    if total_debt > 0 and avg_monthly_payment > 0:
        months_to_payoff = total_debt / avg_monthly_payment
        payoff_date = now + timedelta(days=months_to_payoff * 30)
        
        debt_payoff["months_to_payoff"] = round(months_to_payoff, 1)
        debt_payoff["payoff_date"] = payoff_date.strftime("%B %Y")
        debt_payoff["message"] = f"If you pay {currency_symbol}{avg_monthly_payment:,.0f}/month, you'll be debt-free by {payoff_date.strftime('%B %Y')}."
    elif total_debt > 0:
        debt_payoff["message"] = f"You have {currency_symbol}{total_debt:,.0f} in debt. Start making regular payments to track your payoff timeline."
    else:
        debt_payoff["message"] = "Great job! You have no outstanding debts."
    
    return {
        "cash_flow_forecast": cash_flow_forecast,
        "bill_reminders": bill_reminders[:5],  # Top 5 upcoming bills
        "debt_payoff": debt_payoff,
        "generated_at": now.isoformat()
    }
