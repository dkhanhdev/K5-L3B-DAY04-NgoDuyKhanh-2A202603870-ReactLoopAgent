# Chạy lại lab theo CHECKPOINTS.md — Git Bash

Cấu hình đã kiểm tra kết nối và tool calling thành công:

```bash
export PROVIDER=openrouter
export MODEL=openai/gpt-6-luna
export OPENROUTER_API_KEY=YOUR_KEY
```

Key thật chỉ để trong `.env` local hoặc biến shell. Python không tự đọc `.env`.
Nạp cấu hình ở mỗi terminal mới:

```bash
source .env
```

`providers.py` dùng endpoint OpenRouter cố định và đặt reasoning.effort=none cho
model này để dùng tool calling qua Chat Completions. Không cần OPENAI_BASE_URL
khi PROVIDER=openrouter. Adapter vẫn hỗ trợ các provider ban đầu của đề.

Kết quả cuối: before 93.45/100, after 98.14/100 (22/22 mỗi lượt); bonus
97.6/100, quy đổi 14.64/15 (10/10). 57 tests offline pass.
Chỉ A8 unscored được chạy lại bằng evaluator gốc; xem evaluation_recovery.json
và bản report trước phục hồi để audit. Không sửa tay điểm.

## CP1 — Khám phá hai tools, không cần LLM

```bash
python -X utf8 -c 'import json; from status_tools import StatusTools; print(json.dumps(StatusTools().get_status("github", "Actions"),ensure_ascii=False,indent=2))'
python -X utf8 -c 'import json; from status_tools import StatusTools; print(json.dumps(StatusTools().get_incident_details("cloudflare", "wp49bp8bqo6c"),ensure_ascii=False,indent=2))'
```

get_status tìm chuỗi trong 50 incident gần nhất, trả tối đa 5 mục. Không tìm
thấy không chứng minh không có sự cố. get_incident_details rút gọn timeline;
đọc updates_total, truncated và captured_at để hiểu giới hạn snapshot.

## CP2 — Chạy agent với LLM thật, status snapshot

```bash
python -X utf8 run.py 'GitHub Actions hiện có sự cố không? Hãy kiểm tra incident gần đây.'
```

Kiểm tra status=completed và trace có model → tool → model. Assistant message
được giữ nguyên, mọi tool result trả đúng tool_call_id trước lượt model tiếp.
Một step tính theo model call, không theo số tools. completed không có nghĩa
câu trả lời chắc chắn đúng.

## CP3 — Tests offline

```bash
python -X utf8 -m unittest discover -s tests -v
```

Nếu sandbox Windows lỗi quyền thư mục tạm, chạy cùng bộ tests với temp trong repo:

```bash
python -X utf8 -c "import tempfile,pathlib,unittest; tempfile.tempdir=str(pathlib.Path.cwd()); r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover('tests')); raise SystemExit(not r.wasSuccessful())"
```

Lỗi JSON/tool trả thành observation; lỗi provider/finish bất thường trả error;
hết budget trả max_steps. Tests fake không thay thế eval với model thật.

## CP4 — Baseline đủ 22 case

```bash
python -X utf8 eval_baseline.py --provider "$PROVIDER" --model "$MODEL" --judge-provider "$PROVIDER" --judge-model "$MODEL" --max-steps 8 --workers 1 --output eval_before.json
```

Wrapper gọi evaluator gốc với baselines/agent_before.py, giữ nguyên cases và
grading. Dùng bản baseline riêng vì agent.py hiện là bản đã cải tiến; không dùng
cùng một bản code để tạo cả before và after. Baseline cũng đã có source gate.

Đọc summary, grade.reason, grade.mechanical, answer và trace. Chỉ đạt CP4 khi
22/22 case được chấm và score_0_100 khác null. Kết quả hoàn chỉnh mới nhất và
phân tích nằm trong NOTES.md; các bản chạy dở/model cũ không thay thế kết quả này.

## CP5 — Phân tích lỗi, cải tiến

Case chọn từ trace thật: A5. Model dùng URL đầy đủ còn source gate chấp nhận
shortlink từ get_incident_details. Feedback cũ không chỉ rõ URL cần trích,
model sửa nhiều lần rồi hết bước. Feedback mới gửi danh sách observed_incident_urls
để model dẫn đúng nguồn đã quan sát. Không suy diễn shortlink tương đương URL khác
và không bịa nguồn. Test regression xác minh sửa được trong budget. Lượt cuối không cung cấp tools,
nhắc tổng hợp và gửi URL đã quan sát để tránh gọi lặp đến hết budget.

Chạy lại tests CP3. Đọc NOTES mục 1–3; đối chiếu trace thay vì chỉ tin điểm judge.
Ví dụ nhận xét judge về mốc giờ E5 ở một lượt chạy dở cần kiểm tra lại vì các mốc
đó thực sự có trong metadata của tool.

## CP6 — Eval sau cải tiến, cùng cấu hình

```bash
python -X utf8 evals/run_evals.py --provider "$PROVIDER" --model "$MODEL" --judge-provider "$PROVIDER" --judge-model "$MODEL" --max-steps 8 --workers 1 --output eval_after.json
python -X utf8 check_submission.py
```

Hai file phải cùng config, đủ 22 case. NOTES mục 4–5 so sánh điểm, lỗi, model
calls, token và chi phí usage trả về. Một lần chạy mỗi phiên bản không chứng
minh ổn định hoặc quan hệ nhân quả. check_submission.py chỉ đọc và kiểm tra file;
không tạo điểm hoặc thay cách chấm của đề.

LLM API 429 tạm thời: adapter thử tối đa 4 lần, đọc Retry-After; nếu không có,
chờ lần lượt 15/30/60 giây. Delay lớn hơn 60 giây hoặc lỗi quota cần xử lý bên
ngoài, không retry sớm hơn yêu cầu server. Chạy tuần tự để giảm request dồn.
Không thay lỗi hạ tầng thành điểm 0 hay sửa tay JSON eval.

## Bonus — Sau bài chính

```bash
python -X utf8 -m unittest discover -s bonus -p 'test_*.py' -v
python -X utf8 run.py --bonus --max-steps 16 'Kiểm tra status GitHub, Vercel và npm.'
python -X utf8 evals/run_evals.py --bonus --provider "$PROVIDER" --model "$MODEL" --judge-provider "$PROVIDER" --judge-model "$MODEL" --workers 1 --output eval_bonus.json
python -X utf8 check_submission.py --bonus
```

Cần đủ 10 case được chấm mới có điểm bonus quy đổi. Dùng tools.schemas và
tools.system_prompt; model đọc next_offset khi câu hỏi cần timeline. Status tool
429 giả lập: tối đa hai lần thực thi cùng yêu cầu. Status API live 429: giữ
Retry-After và dừng retry cùng yêu cầu trong run. Các lỗi này khác rate limit LLM.

## CP7 — Demo và nộp

Dùng DEMO.md để mở trace nhiều bước và lỗi thật. Giải thích được code,
không học thuộc output. Tự kiểm tra SUBMISSION.md: repo đúng tên, public, đã push,
không có key và đã nộp link LMS bằng tài khoản cá nhân.

```bash
git ls-files .env .env.example
python -X utf8 check_submission.py --bonus
```

Lệnh git chỉ được thấy .env.example. Phiên làm việc này chuẩn bị code, tests,
eval và tài liệu; không tự xác nhận đã trình bày demo, push hoặc nộp LMS.
