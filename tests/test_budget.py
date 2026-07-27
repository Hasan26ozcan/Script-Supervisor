from datetime import date

import pytest

from app.budget import BudgetExceeded, CostBudget


def test_cost_budget_consumes_and_resets():
    budget = CostBudget(per_run_limit=10.0, daily_limit=20.0)
    budget.consume(3.0, today=date(2026, 7, 26))
    assert budget.run_used == 3.0
    assert budget.daily_used == 3.0

    budget.consume(5.0, today=date(2026, 7, 26))
    assert budget.run_used == 8.0
    assert budget.daily_used == 8.0

    budget.reset_run()
    assert budget.run_used == 0.0
    assert budget.daily_used == 8.0

    budget.reset_daily(today=date(2026, 7, 27))
    assert budget.daily_used == 0.0
    assert budget.current_day == date(2026, 7, 27)


def test_cost_budget_raises_when_limit_exceeded():
    budget = CostBudget(per_run_limit=5.0, daily_limit=10.0)
    budget.consume(4.0, today=date(2026, 7, 26))
    with pytest.raises(BudgetExceeded):
        budget.consume(2.0, today=date(2026, 7, 26))

    budget = CostBudget(per_run_limit=10.0, daily_limit=5.0)
    budget.consume(3.0, today=date(2026, 7, 26))
    with pytest.raises(BudgetExceeded):
        budget.consume(3.0, today=date(2026, 7, 26))
