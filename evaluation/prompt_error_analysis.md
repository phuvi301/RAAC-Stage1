# Báo Cáo Phân Tích Sai Số Prompt v1 (Prompt Error Analysis)
## Dự án RAAC – Requirement-Aware Adaptive Collaboration (Task 1.8)

Báo cáo này tổng hợp kết quả kiểm nghiệm trên **10 issues pilot** đa dạng đại diện cho phổ điểm của 4 trục $R = (C, T, S, I)$, so sánh giữa kết quả chuyên gia (**Human Ground Truth**) và kết quả sinh tự động bởi Requirement Analyzer v1.

---

## 1. Thống kê Sai số Tổng quát trên 10 Issues Pilot

| Trục Đánh Giá | Số mẫu Khớp Hoàn Toàn (Diff = 0) | Chênh lệch +1 (Overestimate) | Chênh lệch -1 (Underestimate) | Chênh lệch $\ge 2$ | Tỷ lệ Khớp Tuyệt Đối | Tỷ lệ Chấp Nhận được ($\|\Delta\| \le 1$) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **C — Complexity** | 8 / 10 | 1 | 1 | 0 | **80%** | **100%** |
| **T — Testability** | 8 / 10 | 1 | 1 | 0 | **80%** | **100%** |
| **S — Security Sensitivity** | 9 / 10 | 0 | 1 | 0 | **90%** | **100%** |
| **I — Architecture Impact** | 7 / 10 | 3 | 0 | 0 | **70%** | **100%** |
| **Tổng thể 40 điểm** | **32 / 40 (80.0%)** | **5 / 40 (12.5%)** | **3 / 40 (7.5%)** | **0 / 40 (0.0%)** | — | **100%** |

---

## 2. Các Mẫu Lỗi Điển Hình và Nguyên Nhân (Failure Patterns)

### 2.1. Hiện tượng Overestimate trục Architecture Impact (I)
- **Triệu chứng:** Ở 3 mẫu (`pallets_flask_3922`, `express_3341`), điểm $I$ bị LLM v1 chấm cao hơn thực tế 1 bậc (chấm 3 thay vì 2, chấm 4 thay vì 3).
- **Nguyên nhân cốt lõi:**
  - LLM bị đánh lừa bởi việc thay đổi tên lỗi (ví dụ đổi exception `KeyError` thành `BuildError`) hoặc cập nhật thư viện phụ thuộc (`path-to-regexp`), xem đây là việc "phá vỡ public API contract".
  - Thực tế trong thiết kế phần mềm, việc chuẩn hóa exception theo đúng tài liệu đặc tả có sẵn hoặc thay thế implementation bên dưới của 1 dependency không làm thay đổi ranh giới kiến trúc (architectural boundary) hay schema dữ liệu.
- **Biện pháp khắc phục trong Prompt v2:** Bổ sung quy tắc phân ranh giới tường minh: *Chỉ chấm $I \ge 4$ khi có sự thay đổi chữ ký hàm của public API làm mã nguồn của người dùng bên ngoài bị lỗi (breaking change), hoặc có migration cấu trúc dữ liệu cốt lõi*.

### 2.2. Hiện tượng Nhầm lẫn giữa Security (S) và Complexity (C)
- **Triệu chứng:** Ở issue `encode_django-rest-framework_5832`, từ khóa `"CSRF"`, `"vulnerability"`, `"CORS"` khiến LLM v1 tự động nâng điểm Complexity từ 3 lên 4.
- **Nguyên nhân cốt lõi:** Hiện tượng "Halo Effect" trong LLM: khi một khía cạnh mang tính rủi ro cao (Security), mô hình có xu hướng suy diễn toàn bộ bài toán là phức tạp (High Complexity).
- **Biện pháp khắc phục trong Prompt v2:** Nhắc lại nguyên tắc phân rã: *Một bản vá bảo mật có thể rất quan trọng ($S=5$) nhưng chỉ cần thêm một dòng kiểm tra điều kiện hoặc xóa một cookie ($C=1..2$). Tuyệt đối không để điểm $S$ làm tăng điểm $C$*.

### 2.3. Hiện tượng Bỏ sót Khó khăn Kiểm thử Số học & Hệ số Tự do (Testability - T)
- **Triệu chứng:** Ở issue `scikit_learn_14092` (KMeans float32 precision loss), LLM v1 chấm $T=3$ trong khi thực tế $T=4$.
- **Nguyên nhân cốt lõi:** Mô hình nghĩ rằng chỉ cần so sánh hai số thực là xong. Tuy nhiên trong Machine Learning / Khoa học tính toán, kiểm thử sai số số học phụ thuộc kiến trúc vi xử lý (x86 vs ARM), compiler flag, và hiện tượng tích lũy sai số làm test case dễ bị flaky (chập chờn).
- **Biện pháp khắc phục trong Prompt v2:** Thêm hướng dẫn đặc thù cho $T$: *Các bài toán liên quan đến sai số số thực, race condition, timeout hoặc phụ thuộc platform phải được xếp vào mức $T \ge 4$*.

---

## 3. Quyết định Điều chỉnh cho Prompt v2

Dựa trên các phân tích trên, Prompt v2 sẽ được tối ưu:
1. **Thêm Negative Guardrails:** Ngăn chặn việc suy luận bắc cầu giữa các trục.
2. **Cụ thể hóa Thang điểm Architecture Impact:** Phân biệt rõ "Sửa đổi tuân thủ spec nội bộ" ($I \le 2$) với "Thay đổi kiến trúc ranh giới" ($I \ge 3$).
3. **Bổ sung Few-shot Example chuyên biệt cho trường hợp $S$ cao nhưng $C$ thấp**.
