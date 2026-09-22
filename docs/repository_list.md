# Danh sách Repository Nguồn Cho Benchmark Dataset (Repository List)
## Dự án RAAC – Requirement-Aware Adaptive Collaboration

Tài liệu này xác định danh sách **8 repository nguồn** được lựa chọn để thu thập dữ liệu benchmark cho Giai đoạn 1 của RAAC. Các repository được lựa chọn dựa trên tiêu chuẩn khắt khe về tính mở, sự đa dạng về ngôn ngữ/kiến trúc, sự hiện diện trong benchmark chuẩn (SWE-bench) và chất lượng liên kết Issue–PR.

---

## 1. Tiêu chí Tuyển chọn Repository

Để bảo đảm tính hợp lệ khoa học và khả năng tổng quát hóa (generalizability) của nghiên cứu:
1. **Có mặt trong SWE-bench hoặc có cấu trúc tương đương:** Thuận tiện cho việc đối chiếu hiệu năng với các nghiên cứu SOTA về LLM Agentic Software Engineering.
2. **Kỷ luật phát triển cao (Strict Development Discipline):** Mọi PR đều có code review, liên kết rõ ràng với Issue, và bắt buộc chạy CI/CD test suite.
3. **Đa dạng về miền ứng dụng (Domain Diversity):** Bao gồm HTTP networking, Web framework, Data processing, Machine learning tooling, Database CLI, API toolkit.
4. **Đa dạng về ngôn ngữ lập trình:** Trọng tâm Python (phổ biến nhất trong SWE-bench) kết hợp TypeScript/JavaScript, Go và Java.
5. **Đa dạng về quy mô thay đổi (Change Size Variance):** Có cả các micro-fixes (1–10 dòng code) lẫn các thay đổi kiến trúc đa module (100–500 dòng code).

---

## 2. Bảng Danh sách Repository Lựa chọn

| # | Repository | Ngôn ngữ | Domain / Loại dự án | SWE-bench | Issue Volume | PR Quality | Lý do lựa chọn & Đặc tính dữ liệu |
|---|---|---|---|:---:|:---:|:---:|---|
| 1 | **`psf/requests`** | Python | Networking / HTTP Client | **Có** | ~6,000+ | Rất cao | Chuẩn mực trong SWE-bench. Đa số issue liên quan đến protocol, redirect, session, stream. Phù hợp cho dải $C \in [1, 4]$, $T \in [1, 3]$. |
| 2 | **`pallets/flask`** | Python | Web Framework / WSGI | **Có** | ~5,000+ | Rất cao | Cấu trúc module rõ ràng (Routing, Context, Request/Response). Có nhiều issue về API contracts, subdomain, error handling. Phổ biến cho $I \in [2, 4]$. |
| 3 | **`encode/django-rest-framework`** | Python | REST API Toolkit | **Có** | ~8,000+ | Rất cao | Chứa nhiều bài toán về Serialization, Authentication, Permission, CSRF. Cung cấp dữ liệu phong phú cho trục Security Sensitivity ($S \in [2, 5]$). |
| 4 | **`scikit-learn/scikit-learn`** | Python / Cython | Machine Learning / Algorithms | **Có** | ~28,000+ | Xuất sắc | Đòi hỏi tính toán thuật toán, ràng buộc toán học, xác minh kết quả số học. Rất giàu mẫu cho độ khó kiểm thử $T \in [3, 5]$ và Complexity cao. |
| 5 | **`marshmallow-code/marshmallow`** | Python | Object Serialization / Validation | **Có** | ~2,200+ | Rất cao | Xử lý schema, parsing, data transformation và exception handling. Rất thích hợp cho các bài toán phân tích logic ràng buộc dữ liệu. |
| 6 | **`expressjs/express`** | JavaScript / Node.js | Web Framework | **Khác** | ~5,500+ | Cao | Dự án nền tảng của hệ sinh thái JS/Node. Cung cấp mẫu đối chiếu đa ngôn ngữ cho Web middleware, routing và HTTP async flow. |
| 7 | **`gin-gonic/gin`** | Go | High-performance Web Engine | **Khác** | ~3,500+ | Cao | Đại diện xuất sắc cho ngôn ngữ tĩnh (static typing) và mô hình concurrency (Goroutines). Rất giá trị để kiểm chứng tính độc lập ngôn ngữ của Requirement Analyzer. |
| 8 | **`elastic/elasticsearch`** (module `rest-high-level`) | Java | Distributed Search & Analytics | **Có** (tương đương) | ~100k+ | Rất cao | Đại diện cho kiến trúc hướng đối tượng enterprise quy mô lớn, phân tán, thay đổi giao diện API sâu rộng. Nguồn mẫu mạnh cho Architecture Impact ($I \in [4, 5]$). |

---

## 3. Chiến lược Khai thác theo Giai đoạn

Để tối ưu hóa thời gian và hạn ngạch GitHub API:

```text
Giai đoạn Pilot (Thử nghiệm ban đầu):
  └── Tập trung vào 3 repo chuẩn:
      1. psf/requests (Networking)
      2. pallets/flask (Web Routing)
      3. encode/django-rest-framework (Auth & API)
      --> Thu thập 30 issues mẫu để clean và chọn 10 issues pilot.

Giai đoạn Benchmark Chính thức (60–100 issues):
  └── Mở rộng sang toàn bộ 5 repo Python (SWE-bench core).

Giai đoạn Đối chiếu Đa Ngôn Ngữ (Expanded Set - nếu mở rộng):
  └── Thu thập thêm các mẫu từ expressjs/express, gin-gonic/gin và elastic/elasticsearch.
```

---

## 4. Đặc tả Truy cập Dữ liệu GitHub API

- **Base URL:** `https://api.github.com/repos/{owner}/{repo}`
- **Endpoints chính:**
  - Lấy danh sách Issue đã đóng: `GET /repos/{owner}/{repo}/issues?state=closed&per_page=100`
  - Lấy thông tin chi tiết Issue: `GET /repos/{owner}/{repo}/issues/{issue_number}`
  - Lấy Timeline sự kiện (xác định cross-referenced PR): `GET /repos/{owner}/{repo}/issues/{issue_number}/timeline`
  - Lấy thông tin PR đã merge: `GET /repos/{owner}/{repo}/pulls/{pull_number}`
  - Lấy danh sách files thay đổi trong PR: `GET /repos/{owner}/{repo}/pulls/{pull_number}/files`
