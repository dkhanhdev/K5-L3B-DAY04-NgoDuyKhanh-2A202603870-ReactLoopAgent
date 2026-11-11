"""Chạy evaluator gốc với bản agent trước cải tiến prompt/retry/bonus."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'evals'))
import run_evals
from baselines.agent_before import run_agent


if __name__ == '__main__':
    run_evals.run_agent = run_agent
    sys.exit(run_evals.main())
