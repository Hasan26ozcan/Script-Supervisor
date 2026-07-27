"""Architecture hardening helpers for cost budgeting."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


class BudgetExceeded(Exception):
    """Raised when a configured cost budget is exceeded."""


@dataclass
class CostBudget:
    per_run_limit: float | None = None
    daily_limit: float | None = None
    run_used: float = 0.0
    daily_used: float = 0.0
    current_day: date | None = None

    def _ensure_day(self, today: date) -> None:
        if self.current_day != today:
            self.current_day = today
            self.daily_used = 0.0

    def consume(self, amount: float, today: date | None = None) -> None:
        today = today or date.today()
        self._ensure_day(today)
        if amount < 0:
            raise ValueError("Budget consumption amount must be non-negative")

        if self.per_run_limit is not None and self.run_used + amount > self.per_run_limit:
            raise BudgetExceeded(
                f"Per-run budget exceeded: {self.run_used + amount:.6f} > {self.per_run_limit:.6f}"
            )
        if self.daily_limit is not None and self.daily_used + amount > self.daily_limit:
            raise BudgetExceeded(
                f"Daily budget exceeded: {self.daily_used + amount:.6f} > {self.daily_limit:.6f}"
            )

        self.run_used += amount
        self.daily_used += amount

    def reset_run(self) -> None:
        self.run_used = 0.0

    def reset_daily(self, today: date | None = None) -> None:
        today = today or date.today()
        self.current_day = today
        self.daily_used = 0.0

    def to_dict(self) -> dict[str, float | None]:
        return {
            "per_run_limit": self.per_run_limit,
            "daily_limit": self.daily_limit,
            "run_used": self.run_used,
            "daily_used": self.daily_used,
            "current_day": self.current_day.isoformat() if self.current_day else None,
        }
