# Báo cáo Đánh giá Chống Thiên Lệch Dataset (Anti-bias Audit Report)
**Quy mô Benchmark hiện tại:** 104 issues

---

## 1. Phân bố theo Repository (Repository Balance)
| Repository | Số lượng Issue | Tỷ lệ (%) |
|---|---|---|
| `encode/django-rest-framework` | 40 | 38.5% |
| `pallets/flask` | 38 | 36.5% |
| `psf/requests` | 26 | 25.0% |

## 2. Phân bố Quy mô Thay đổi Mã nguồn (LOC Bins)
Đo lường tính đa dạng độ phức tạp ($C$) và tác động kiến trúc ($I$):
| Phân tầng kích thước | Số lượng Issue | Tỷ lệ (%) | Ý nghĩa đánh giá |
|---|---|---|---|
| **Micro (1-5 LOC)** | 13 | 12.5% | Bug nhỏ cục bộ (C=1, I=1), kiểm thử cộng tác L1 |
| **Small (6-20 LOC)** | 22 | 21.2% | Tinh chỉnh logic đơn lẻ (C=2, I=1..2) |
| **Medium (21-100 LOC)** | 41 | 39.4% | Tính năng nhỏ / Sửa nhiều hàm (C=3, I=2..3) |
| **Large (>100 LOC)** | 28 | 26.9% | Tái cấu trúc / Kiến trúc sâu (C=4..5, I=4..5) |

## 3. Phân bố Khả năng Kiểm thử (Testability Balance)
- **Số issue có Unit/Integration Test đi kèm:** 74 (71.2%)
- **Số issue không có Test (cần manual/env test):** 30 (28.8%)
- *Nguyên tắc RAAC:* Giữ lại cả 2 nhóm để đo lường công bằng trục $T$ (Testability).

## 4. Đa dạng Loại Yêu cầu (Category Diversity)
| Danh mục | Số lượng | Tỷ lệ (%) |
|---|---|---|
| Bug Fix | 73 | 70.2% |
| Feature / Enhancement | 20 | 19.2% |
| Refactor / Performance | 1 | 1.0% |
| Security / CVE | 4 | 3.8% |
| Other | 6 | 5.8% |

## 5. Đánh giá Tổng thể & Khuyến nghị (Anti-bias Scorecard)
- **Đa dạng nguồn:** [x] ĐẠT (Hiện có 3 repositories)
- **Tránh độc quyền Repo:** [x] ĐẠT (Không repo nào vượt 50%)
- **Bao phủ phổ điểm độ khó:** [x] ĐẠT (Đầy đủ từ Micro đến Large)
- **Cân bằng Testability:** [x] ĐẠT (Có cả bài có test và không có test)

🎉 **Kết luận:** Bộ dữ liệu đạt chuẩn Chống Thiên Lệch (Unbiased Benchmark) theo Rubric RAAC Phase 1!
