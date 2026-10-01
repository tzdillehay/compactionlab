"""Public draft calculator; never authorizes or executes financial transactions."""


def draft_snowball(balances, minimums, budget):
    if not balances or set(balances) != set(minimums):
        raise ValueError("Matching account names are required")
    values = [*balances.values(), *minimums.values(), budget]
    if any(type(value) is not int or value < 0 for value in values):
        raise ValueError("Amounts must be nonnegative integer cents")
    payments = {name: min(minimums[name], balance) for name, balance in balances.items()}
    total_minimums = sum(payments.values())
    if budget < total_minimums:
        raise ValueError("Budget is below total minimum payments")
    remaining = budget - total_minimums
    target = min(balances, key=lambda name: (balances[name], name))
    for name in sorted(balances, key=lambda name: (balances[name], name)):
        headroom = balances[name] - payments[name]
        allocation = min(remaining, headroom)
        payments[name] += allocation
        remaining -= allocation
    return {
        "budget_cents": budget,
        "minimums_cents": total_minimums,
        "extra_cents": budget - total_minimums,
        "target": target,
        "payments": payments,
        "unallocated_cents": remaining,
    }
