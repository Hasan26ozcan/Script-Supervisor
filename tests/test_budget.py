"""Tests for the CostBudget module."""
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


def test_cost_budget_no_limits():
    budget = CostBudget(per_run_limit=None, daily_limit=None)
    budget.consume(100.0, today=date(2026, 7, 26))
    assert budget.run_used == 100.0
    assert budget.daily_used == 100.0

    budget.consume(200.0, today=date(2026, 7, 26))
    assert budget.run_used == 300.0


def test_cost_budget_negative_consumption_raises():
    budget = CostBudget(per_run_limit=10.0)
    with pytest.raises(ValueError, match="non-negative"):
        budget.consume(-1.0, today=date(2026, 7, 26))


def test_cost_budget_auto_daily_reset_on_new_day():
    budget = CostBudget(per_run_limit=10.0, daily_limit=5.0)
    budget.consume(4.0, today=date(2026, 7, 26))
    assert budget.daily_used == 4.0

    # Next day — daily_used should reset automatically
    budget.consume(3.0, today=date(2026, 7, 27))
    assert budget.daily_used == 3.0
    assert budget.run_used == 7.0  # run_used accumulates across days


def test_cost_budget_daily_limit_on_new_day():
    budget = CostBudget(per_run_limit=None, daily_limit=5.0)
    budget.consume(4.0, today=date(2026, 7, 26))
    # This should NOT raise — new day resets the daily counter
    budget.consume(3.0, today=date(2026, 7, 27))
    assert budget.daily_used == 3.0


def test_cost_budget_to_dict():
    budget = CostBudget(per_run_limit=10.0, daily_limit=20.0)
    budget.consume(3.0, today=date(2026, 7, 26))
    d = budget.to_dict()
    assert d["per_run_limit"] == 10.0
    assert d["daily_limit"] == 20.0
    assert d["run_used"] == 3.0
    assert d["daily_used"] == 3.0
    assert d["current_day"] == "2026-07-26"
