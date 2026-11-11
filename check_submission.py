"""Kiểm tra file eval theo CP4/CP6; chỉ đọc, không thay điểm hoặc dữ liệu."""
import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def check_report(filename, dataset):
    path = ROOT / filename
    if not path.exists():
        print(f'CHƯA ĐẠT: thiếu {filename}')
        return None
    try:
        report = json.loads(path.read_text(encoding='utf-8'))
        reference = ROOT / ('bonus/cases.json' if dataset == 'bonus' else 'evals/cases.json')
        expected = {case['id'] for case in json.loads(reference.read_text(encoding='utf-8'))}
        cases = report['cases']
        ids = [case['id'] for case in cases]
        if len(ids) != len(expected) or set(ids) != expected:
            raise ValueError('thiếu, trùng hoặc sai ID case')
        scores = [case['grade'].get('score') for case in cases]
        scored = sum(case['grade'].get('status') == 'scored' and score is not None
                     for case, score in zip(cases, scores))
        if scored != len(expected):
            raise ValueError(f'mới chấm {scored}/{len(expected)} case')
        if any(type(score) not in (int, float) or not math.isfinite(score)
               or not 0 <= score <= 100 for score in scores):
            raise ValueError('điểm case không hợp lệ')
        summary = report['summary']
        mean = sum(scores) / len(scores)
        overall = summary.get('score_0_100')
        if (type(overall) not in (int, float) or not math.isfinite(overall)
                or abs(overall - mean) > 0.011):
            raise ValueError('điểm tổng null hoặc không khớp điểm case')
        if (summary.get('total_cases') != len(expected)
                or summary.get('scored_cases') != len(expected)
                or summary.get('unscored_cases') != 0):
            raise ValueError('summary không khớp số case')
        config = report['config']
        if config.get('dataset') != dataset:
            raise ValueError('sai dataset')
        if dataset == 'bonus':
            bonus = summary.get('bonus_points_0_15')
            if type(bonus) not in (int, float) or abs(bonus - round(overall * .15, 2)) > .001:
                raise ValueError('chưa có điểm bonus hợp lệ')
        print(f'ĐẠT: {filename}: {scored}/{len(expected)} case; {overall}/100')
        return config
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        print(f'CHƯA ĐẠT: {filename}: {exc}')
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bonus', action='store_true', help='Kiểm tra thêm 10 case bonus')
    args = parser.parse_args()
    before = check_report('eval_before.json', 'core')
    after = check_report('eval_after.json', 'core')
    ok = before is not None and after is not None
    if ok and before != after:
        print('CHƯA ĐẠT CP6: config trước và sau khác nhau')
        ok = False
    if args.bonus:
        bonus = check_report('eval_bonus.json', 'bonus')
        ok = bonus is not None and ok
    print('Cần kiểm tra thủ công NOTES, demo, repo public, bảo mật key và nộp LMS theo CP7.')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
