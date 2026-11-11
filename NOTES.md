# Ghi chú phân tích · Day 04

Họ và tên: Ngô Duy Khánh
MSSV: 2A202603870

## 1. Case được chọn

Chọn A5: yêu cầu danh sách đầy đủ incident GitHub Actions năm 2025.
Baseline dùng OpenRouter / openai/gpt-6-luna, 22/22 case được chấm, điểm 93.45/100.
A5 có status=max_steps, điểm 0, đã gọi model 8 lần. Câu trả lời cuối không bịa
danh sách và biết snapshot không đủ để kết luận, nhưng không vượt source gate.

Trích câu trả lời cuối baseline:

> Mình không thể lập danh sách **đầy đủ** các incident GitHub Actions trong năm 2025 từ dữ liệu đã truy vấn. Snapshot GitHub Status lúc **2026-11-09 03:50 UTC** chỉ bao gồm tối đa 50 incident gần nhất; công cụ lưu ý rằng không thấy incident trong kết quả không chứng minh là không có.
>
> Một URL incident có trong dữ liệu truy vấn: https://www.githubstatus.com/incidents/xr3myzj7ms51. Incident này được tạo ngày 4-11-2026, nên không phải incident năm 2025.
>
> **Độ đầy đủ của kết quả cho năm 2025: không xác định.**

## 2. Bằng chứng trong trace

Nguồn: eval_before.json, cases[id=A5].result.trace.

```text
step 1: get_status(github, Actions)
step 2: get_status(github)
step 3: get_incident_details(t89g2q1800fr), url=https://stspg.io/lv4q3xm9r0rk
step 4: get_incident_details(h02n9572mx9y), url=https://stspg.io/7pwv28hvkmz8
step 5: get_incident_details(xr3myzj7ms51), url=https://stspg.io/pjgptg3cfc6n
steps 6, 7, 8: finish=stop, rồi validation_missing_source
status=max_steps, grade.score=0
```

Final answer dùng https://www.githubstatus.com/incidents/xr3myzj7ms51,
trong khi gate chỉ chấp nhận các URL từ trường url của get_incident_details.
Link dài xuất hiện trong nội dung update nhưng không thuộc tập URL gate nhận.
Feedback cũ chỉ yêu cầu thêm nguồn mà không nêu URL nào được chấp nhận.
Model sửa nhiều lần vẫn không vượt gate. Đây là lỗi tương tác loop/validation,
không phải bằng chứng model đã bịa incident năm 2025.

## 3. Thay đổi đã thực hiện

- agent.py: feedback validation gửi observed_incident_urls, yêu cầu dẫn nguyên
  văn một URL đã quan sát. Không tự coi shortlink và URL đầy đủ là tương đương,
  không chế tạo URL để vượt kiểm tra.
- Dành lượt cuối trong max_steps để tổng hợp: không cung cấp tools cho lượt đó,
  nhắc model nêu giới hạn bằng chứng và gửi kèm URL nguồn đã quan sát. Không tăng
  max_steps để làm case pass. Nếu model vẫn không hoàn tất hợp lệ, trả max_steps/error.
- Prompt phân biệt components với dịch vụ chỉ được nhắc trong update; không
  suy ra mọi incident đã resolved từ danh sách giới hạn.
- Bonus dùng schemas/system_prompt riêng, trả đủ tool results, hỗ trợ offset/
  next_offset, giới hạn retry 429 của status tools và không suy lỗi truy cập thành outage.
- providers.py: OpenRouter reasoning.effort=none cho openai/gpt-6-luna. Retry LLM
  429 tối đa 4 attempts; tôn trọng Retry-After, không retry sớm nếu delay >60 giây,
  không retry lỗi insufficient_quota. Chạy eval tuần tự để giảm request dồn.
- Các khả năng adapter OpenAI-compatible đã thêm trước đó vẫn giữ: base URL,
  User-Agent riêng, session header cho OpenCode. API đang dùng thực tế là OpenRouter.
- Không thay fixtures, cases, scenarios, grading hoặc rubric. Baseline code được
  giữ ở baselines/agent_before.py, dùng chung adapter với bản cải tiến.

Tests: 54 tests trong tests/ và 3 tests agent bonus đều pass (57 tổng).
Regression tests kiểm tra repair URL khác alias, lượt cuối dành cho final,
retry có giới hạn, Retry-After dài/quota, 5 provider results và pagination.

## 4. So sánh hai lần chạy

Cả hai config giống nhau: provider/judge=openrouter, model/judge_model=
openai/gpt-6-luna, dataset=core, max_steps=8, cùng snapshot. Hai bản code khác nhau.

| Chỉ số | eval_before.json | eval_after.json |
|---|---|---|
| Đã chấm | 22/22 | 22/22 |
| Điểm | 93.45 | 98.14 |
| A5 | 0 / max_steps | 95 / completed |
| Agent logical calls có usage | 67 | 71 |
| Agent tokens | 76770 | 90500 |
| Judge tokens | 42182 | 46373 |
| Chi phí usage trả về (USD) | 0.016012 | 0.018378 |

Điểm tổng tăng 4.69. A5 hoàn tất thay vì hết budget. Trong bản after đã chọn,
H1 đạt 96 và completed; E4/E5 đạt 100. Không khẳng định mọi case đều tăng.
Chi phí bảng trên chỉ cộng usage của hai report này, không gồm smoke check,
các lượt chạy dở hoặc các request retry không có usage; không phải hóa đơn cuối.
Logical calls là lượt provider.complete, không phải số HTTP attempts khi retry.

A8 của lượt after ban đầu bị judge trả JSON kèm dữ liệu dư (Extra data), không
có điểm. Chỉ case unscored này được gọi lại bằng run_evals.run_case và chấm bằng
grading gốc cùng config; không chọn lại case vì điểm thấp và không sửa tay điểm.
Bản trước phục hồi ở baselines/eval_after_before_infrastructure_recovery.json;
evaluation_recovery.json ghi case được chạy lại. Summary tính bằng summarize gốc.

Bảng đủ 22 case:

| Case | Before | After |
|---|---|---|
| E1 | 92 | 95 |
| E2 | 99 | 100 |
| E3 | 100 | 99 |
| E4 | 94 | 100 |
| E5 | 93 | 100 |
| E6 | 100 | 100 |
| A1 | 97 | 95 |
| A2 | 100 | 100 |
| A3 | 99 | 100 |
| A4 | 100 | 100 |
| A5 | 0 | 95 |
| A6 | 95 | 96 |
| A7 | 100 | 96 |
| A8 | 99 | 97 |
| H1 | 93 | 96 |
| H2 | 100 | 100 |
| H3 | 99 | 100 |
| H4 | 100 | 100 |
| H5 | 98 | 93 |
| H6 | 99 | 98 |
| H7 | 99 | 99 |
| H8 | 100 | 100 |

## 5. Giới hạn

- Judge có thể sai và thiên lệch khi cùng model với agent. Ở một lượt chạy dở,
  judge nói E5 không có mốc giờ nhưng metadata tool thực tế chứa các mốc này;
  cần đọc trace thay vì tối ưu mù theo điểm.
- Một lần chạy mỗi phiên bản không chứng minh ổn định hoặc quan hệ nhân quả.
  Nhiều thay đổi prompt/validation cùng tồn tại, không quy toàn bộ chênh lệch
  chỉ cho một thay đổi. Một số case có thể giảm điểm do diễn giải/biến thiên judge.
- Source gate chỉ kiểm tra có một URL đã quan sát, không xác minh mọi claim hoặc
  nguồn riêng cho từng provider. Snapshot, tìm trong 50 incident và truncation
  không thay thế dữ liệu lịch sử đầy đủ hoặc trạng thái live.
- Lượt cuối có thể cho câu trả lời chưa đủ chi tiết; phải báo rõ phần thiếu,
  không coi việc completed là chứng minh câu trả lời đúng.
- Pagination/lọc nhiễu vẫn do model điều khiển. Retry status tool và retry LLM API
  là hai lớp khác nhau, đều có giới hạn.
- Trạng thái push xem lịch sử Git của repo. CP7 vẫn cần trình bày demo và nộp link LMS bằng tài khoản cá nhân.

## Bonus — kết quả thật

Đã chấm đủ 10/10 case, điểm 97.6/100,
quy đổi 14.64/15 theo evaluator gốc.
Tổng token usage agent+judge: 122616;
chi phí usage ghi nhận: $0.012540.
Đây là điểm tham khảo, không tự cộng với điểm bài lab chính do giảng viên chấm.

| Case | Điểm |
|---|---|
| B1 | 100 |
| B2 | 100 |
| B3 | 100 |
| B4 | 100 |
| B5 | 90 |
| B6 | 97 |
| B7 | 100 |
| B8 | 94 |
| B9 | 100 |
| B10 | 95 |

Lỗi/giới hạn còn lại theo judge (cần tự đối chiếu trace):

- B5 (90): Thông tin incident, trạng thái resolved, component, thời gian và URL khớp kết quả tool. Câu trả lời nêu đủ 3/3 cập nhật, nhưng trace cho thấy lần gọi đầu thất bại và lần gọi sau vẫn dùng offset/limit giống hệt; không thực sự sửa định dạng như yêu cầu. Phần tóm tắt timeline khớp hai cập nhật đã nêu nhưng bỏ qua nội dung cập nhật investigating ngoài việc nói đã đọc đủ ba.
- B6 (97): Trạng thái và incident mới nhất cho cả hai dịch vụ, phạm vi, thời gian và liên kết nguồn đều khớp trace; không suy diễn quan hệ nhân quả. Có một điểm nhỏ: câu trả lời nói kết quả tìm kiếm tối đa 8 mục mỗi dịch vụ, trong khi mục tiêu yêu cầu bỏ qua 160 mục nhiễu; Vercel trace cũng ghi match_count 16, không phải tổng số mục đã xét.
- B8 (94): Nêu đúng cả hai incident đã resolved, tác động khác nhau, mốc thời gian, hai URL chi tiết và thận trọng không quy cùng nguyên nhân. Có một điểm diễn đạt chưa chính xác: nói Vercel update cuối “xác nhận backlog build đã được xử lý” là đúng, nhưng ngụ ý nguyên nhân Vercel chưa được nêu chỉ dựa trên update đã xem; đây là cách diễn đạt có giới hạn phù hợp. Thời điểm tra cứu và trạng thái tổng thể là thông tin thêm, nhất quán với trace.
- B10 (95): Tổng hợp đúng status của cả năm nhà cung cấp, các timestamp snapshot, incident và phạm vi được nêu phù hợp trace; nhận diện rõ Cloudflare có snapshot cũ và không quy kết chung nguyên nhân. Nêu các nguồn liên kết và việc Vercel gặp 429 rồi retry thành công, không vượt giới hạn. Một chi tiết sai nhỏ: nói incident GitHub có thể có cập nhật trạng thái job chậm, trong khi nội dung này gắn với incident liên quan; incident được chọn chỉ ghi nhận suy giảm availability của Actions. Ngoài ra, câu về Cloudflare incident Wrangler/Pages/Workers Builds diễn giải thành lỗi upload/deploy, gần với mô tả nguồn nhưng nguồn nói failed uploads và deployments, không giải thích thêm.
