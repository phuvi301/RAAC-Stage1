# Báo Cáo Chiến Lược Quy Mô Benchmark & Phân Bố Mẫu (Task 1.6)
## Dự án RAAC – Requirement-Aware Adaptive Collaboration

Báo cáo này giải quyết điểm cần thống nhất về số lượng mẫu benchmark giữa Checklist Giai đoạn 1 (60–100 issues) và Rubric Đề tài (150–200 issues), đồng thời đề ra chiến lược giám sát phân bố đa dạng trên 4 trục $R = (C, T, S, I)$.

---

## 1. Phân Tích Sự Khác Biệt về Quy Mô Benchmark

| Tài liệu tham chiếu | Số lượng đề xuất | Ưu điểm | Thách thức nguồn lực |
|---|:---:|---|---|
| **Checklist TV1 (Giai đoạn 1)** | **60–100 issues** | Vừa sức cho nhóm 3 người trong lộ trình 36 tuần. Cho phép thực hiện đầy đủ đánh giá chéo 2 annotators/issue mà không bị quá tải. | Cần chọn lọc kỹ để đại diện đủ mọi tổ hợp $(C, T, S, I)$. |
| **Rubric Phase 1.2 (Tổng thể đề tài)** | **150–200 issues** | Mẫu lớn hơn, tăng độ tin cậy thống kê khi train Adaptive Controller ở Giai đoạn 3 (Decision Tree / Gradient Boosting). | Chi phí gọi LLM và khối lượng gán nhãn thủ công (Human Annotation) rất lớn (~400 lượt chấm). |

---

## 2. Chiến Lược Quy Mô 3 Tầng Được Đề Xuất (Phù Hợp Nhất)

Để cân bằng giữa chất lượng nghiên cứu và năng lực thực thi, nhóm TV1 đề xuất triển khai theo mô hình 3 tầng (3-tier roadmap):

```text
               ┌──────────────────────────────────────────────┐
               │         TẦNG 1: PILOT BENCHMARK              │
               │   Quy mô: 10 issues đại diện 4 trục          │
               │   Mục đích: Test Prompt v1 vs Human Ground   │
               │   Trạng thái: ĐÃ HOÀN THÀNH (Task 1.8)       │
               └──────────────────────┬───────────────────────┘
                                      │
                                      ▼
               ┌──────────────────────────────────────────────┐
               │        TẦNG 2: INITIAL CORE BENCHMARK        │
               │   Quy mô: 80 issues (60–100 issues)          │
               │   Mục đích: Chạy Adaptivity Ladder (L1-L4)   │
               │             và tạo Oracle Benchmark GĐ 2    │
               │   Thời gian: Tuần 4–7 Giai đoạn 1            │
               └──────────────────────┬───────────────────────┘
                                      │
                                      ▼
               ┌──────────────────────────────────────────────┐
               │       TẦNG 3: EXPANDED BENCHMARK (Tùy chọn)  │
               │   Quy mô: 150–200 issues                     │
               │   Mục đích: Mở rộng train Controller GĐ 3    │
               │   Thời gian: Triển khai khi đã ổn định L1-L4 │
               └──────────────────────────────────────────────┘
```

---

## 3. Khung Giám Sát Phân Bố Mẫu 4 Trục (Distribution Targets)

Để tránh hiện tượng dataset bị lệch (skewed) về các task quá đơn giản ($C=1, I=1$) hoặc quá khó, TV1 đặt mục tiêu phân bổ tỷ lệ cho bộ Core Benchmark (80 issues):

| Thang điểm (Score) | C — Complexity | T — Testability | S — Security Sensitivity | I — Architecture Impact |
|:---:|:---:|:---:|:---:|:---:|
| **Mức 1 (Rất thấp / Cục bộ)** | 15% (12 issues) | 20% (16 issues) | **50% (40 issues)** *(Bình thường phần mềm không đổi auth)* | 35% (28 issues) |
| **Mức 2 (Thấp / Module)** | 25% (20 issues) | 30% (24 issues) | 20% (16 issues) | 30% (24 issues) |
| **Mức 3 (Trung bình / Ranh giới)** | 30% (24 issues) | 25% (20 issues) | 15% (12 issues) | 20% (16 issues) |
| **Mức 4 (Cao / Khó)** | 20% (16 issues) | 15% (12 issues) | 10% (8 issues) | 10% (8 issues) |
| **Mức 5 (Rất cao / Tối quan trọng)** | 10% (8 issues) | 10% (8 issues) | 5% (4 issues) | 5% (4 issues) |
| **Tổng cộng** | **100% (80 issues)** | **100% (80 issues)** | **100% (80 issues)** | **100% (80 issues)** |

> **Ghi chú phối hợp với TV3:** TV1 sẽ xuất bảng histogram phân bố điểm số sau khi crawl và làm sạch để TV3 kiểm tra tính đa dạng trước khi bắt đầu đợt gán nhãn chính thức.
