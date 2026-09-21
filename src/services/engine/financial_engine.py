import json
from src.config.settings import SCHEME_RULES_PATH


def calculate_financial_plan(margin_money: float) -> dict:
    """
    Calculates the financial plan for loan applications under concessional schemes (NSFDC/NBCFDC).
    
    :param margin_money: The entrepreneur's margin contribution (float)
    :return: A dictionary containing project cost, loan amount, scheme details, quarterly EMI,
             and the quarter-by-quarter reducing balance repayment schedule.
             Returns {"error": "invalid margin money"} if margin_money <= 0.
             Returns {"error": "scheme rules file missing or invalid"} if json file cannot be loaded.
             Returns {"error": "exceeds scheme limit"} if project cost exceeds limits.
             Returns {"error": "invalid scheme tenure"} if tenure_years <= 0.
    """
    if margin_money <= 0:
        return {"error": "invalid margin money"}

    rules_path = SCHEME_RULES_PATH
    try:
        with open(rules_path, "r", encoding="utf-8") as f:
            scheme_rules = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"error": "scheme rules file missing or invalid"}

    for scheme_name, rules in scheme_rules.items():
        moratorium_months = rules.get("moratorium_months", 0)
        if moratorium_months % 3 != 0:
            raise ValueError(
                f"Scheme '{scheme_name}' has moratorium_months={moratorium_months} which is not divisible by 3 (must align to quarters)"
            )

    project_cost = margin_money / 0.10
    loan_amount = project_cost * 0.90

    sorted_schemes = sorted(
        scheme_rules.items(),
        key=lambda item: item[1].get("max_project_cost", float("inf"))
    )

    selected_scheme_name = None
    selected_scheme_rules = None

    for scheme_name, rules in sorted_schemes:
        if project_cost <= rules.get("max_project_cost", float("inf")):
            selected_scheme_name = scheme_name
            selected_scheme_rules = rules
            break

    if not selected_scheme_rules:
        return {"error": "exceeds scheme limit"}

    interest_rate_pa = selected_scheme_rules["interest_rate_pa"]
    tenure_years = selected_scheme_rules["tenure_years"]
    moratorium_months = selected_scheme_rules["moratorium_months"]

    if tenure_years <= 0:
        return {"error": "invalid scheme tenure"}

    # tenure_years is the TOTAL loan life stated by the scheme (e.g. "7 years
    # including a 6-month moratorium") — the moratorium is part of it, not
    # additional time. So the EMI-paying period is tenure minus moratorium.
    moratorium_quarters = moratorium_months // 3
    total_quarters = (tenure_years * 4) - moratorium_quarters

    quarterly_rate = interest_rate_pa / 4.0
    if quarterly_rate == 0:
        quarterly_emi = round(loan_amount / total_quarters, 2)
    else:
        emi_factor = (1.0 + quarterly_rate) ** total_quarters
        raw_emi = loan_amount * quarterly_rate * emi_factor / (emi_factor - 1.0)
        quarterly_emi = round(raw_emi, 2)

    balance = loan_amount
    repayment_schedule = []

    for i in range(1, total_quarters + 1):
        q_num = moratorium_quarters + i
        interest = round(balance * quarterly_rate, 2)

        if i == total_quarters:
            principal = round(balance, 2)
            emi = round(principal + interest, 2)
            balance = 0.0
        else:
            emi = quarterly_emi
            principal = round(emi - interest, 2)
            balance = round(balance - principal, 2)

        repayment_schedule.append({
            "quarter": q_num,
            "principal": principal,
            "interest": interest,
            "emi": emi
        })

    return {
        "project_cost": project_cost,
        "loan_amount": loan_amount,
        "scheme_name": selected_scheme_name,
        "interest_rate_pa": interest_rate_pa,
        "tenure_years": tenure_years,
        "moratorium_months": moratorium_months,
        "quarterly_emi": quarterly_emi,
        "repayment_schedule": repayment_schedule
    }


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    test_margins = [10000, 100000, 500000, 0, -5000, 600000]

    for margin in test_margins:
        print("=" * 70)
        print(f"Testing for Margin Money: ₹{margin:,.2f}")
        plan = calculate_financial_plan(margin)
        if "error" in plan:
            print(f"Result: {plan}")
        else:
            print(f"Project Cost:     ₹{plan['project_cost']:,.2f}")
            print(f"Loan Amount:      ₹{plan['loan_amount']:,.2f}")
            print(f"Scheme Name:      {plan['scheme_name']}")
            print(f"Interest Rate:    {plan['interest_rate_pa'] * 100:.2f}% p.a.")
            print(f"Tenure:           {plan['tenure_years']} years ({plan['tenure_years'] * 4} quarters)")
            print(f"Moratorium:       {plan['moratorium_months']} months ({plan['moratorium_months'] // 3} quarters)")
            print(f"Quarterly EMI:    ₹{plan['quarterly_emi']:,.2f}")
            print(f"Total Quarters in Schedule: {len(plan['repayment_schedule'])}")
            
            if plan['repayment_schedule']:
                print("\nSample Repayment Schedule (First 3 & Last 2 quarters):")
                sched = plan['repayment_schedule']
                sample = sched[:3] + ([None] if len(sched) > 5 else []) + (sched[-2:] if len(sched) > 5 else sched[3:])
                for item in sample:
                    if item is None:
                        print("  ...")
                    else:
                        print(f"  Quarter {item['quarter']:2d} | Principal: ₹{item['principal']:>10,.2f} | Interest: ₹{item['interest']:>8,.2f} | EMI: ₹{item['emi']:>10,.2f}")
        print("=" * 70)
        print()
