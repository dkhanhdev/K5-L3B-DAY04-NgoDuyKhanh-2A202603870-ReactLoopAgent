# Demo CP7 — dùng kết quả OpenRouter mới

## Trace nhiều bước: E2 của bản cải tiến

```bash
python -X utf8 -c 'import json; d=json.load(open("eval_after.json",encoding="utf-8")); c=next(x for x in d["cases"] if x["id"]=="E2"); print(json.dumps(c["result"],ensure_ascii=False,indent=2))'
```

Giải thích: get_status tìm incident, get_incident_details kiểm tra phạm vi
FedRAMP, final dẫn nguồn và không suy ra nguyên nhân lỗi website CLB. Kiểm tra
các step, arguments, observations, tool_call_id trong code, timestamp snapshot.
Mọi calls của assistant phải có tool results trước model call tiếp theo.

## Lỗi thật và cải tiến: A5

```bash
python -X utf8 -c 'import json; ds=[json.load(open(p,encoding="utf-8")) for p in ["eval_before.json","eval_after.json"]]; [print(json.dumps(next(c for c in d["cases"] if c["id"]=="A5"),ensure_ascii=False,indent=2)) for d in ds]'
```

Before: shortlink trong trường url khác URL đầy đủ model dùng. Feedback thiếu
URL cụ thể, source gate lặp ở bước 6/7/8, hết budget và 0 điểm. After: feedback có
observed_incident_urls và lượt cuối dành để tổng hợp; A5 completed, đạt 95.
Nêu giới hạn 50 incident gần nhất và không bịa danh sách đầy đủ năm 2025.

Dẫn NOTES để so sánh 22 case, token/chi phí, hạn chế của judge và dữ liệu.
Không gọi API lại khi chỉ cần trình bày trace đã lưu. Tests fake không chứng
minh chất lượng thực tế; completed không có nghĩa mọi claim đều đúng.

CP7 chỉ hoàn thành sau khi bạn trình bày được code/trace, push repo public và
nộp link LMS. Tài liệu demo này không phải xác nhận đã nộp.
