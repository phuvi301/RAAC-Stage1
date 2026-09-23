# SỔ TAY VẬN HÀNH & KẾT QUẢ TRIỂN KHAI: TV1 – DATA & REQUIREMENT ANALYZER
## Đề tài Nghiên cứu: Requirement-Aware Adaptive Collaboration (RAAC)
### Giai đoạn 1: Benchmark Dataset & Requirement Analyzer Pipeline

> **Vai trò:** TV1 – Data & Requirement Analyzer Lead  
> **Mục tiêu cốt lõi:** Xây dựng tập dữ liệu benchmark phần mềm chuẩn hóa và pipeline Requirement Analyzer tự động chuyển đổi GitHub Issue thành **Requirement Profile**:
> $$\mathbf{R} = (C, T, S, I) \in \{1, 2, 3, 4, 5\}^4$$
> trong đó:
> - **$C$ (Complexity):** Độ phức tạp lập kế hoạch và triển khai mã nguồn (1–5).
> - **$T$ (Testability):** Mức độ thách thức kiểm thử và cô lập test oracle tự động (1–5).
> - **$S$ (Security Sensitivity):** Mức độ nhạy cảm bảo mật, quyền hạn và rủi ro an toàn (1–5).
> - **$I$ (Architecture Impact):** Mức độ tác động ranh giới module, public contracts và schema (1–5).
> 
> *Quy tắc bất biến:* Thang điểm 1–5 là thang thứ bậc (ordinal scale), chấm điểm hoàn toàn độc lập và **tuyệt đối không cộng gộp thành một điểm tổng**.

---

## MỤC LỤC

1. [Tổng quan Tiến độ 9 Tasks của TV1](#1-tổng-quan-tiến-độ-9-tasks-của-tv1)
2. [Chi tiết Triển khai Từng Task (Task 1.1 → Task 1.9)](#2-chi-tiết-triển-khai-từng-task)
   - [Task 1.1: Viết tiêu chí lọc issue](#task-11-viết-tiêu-chí-lọc-issue)
   - [Task 1.2: Chọn 5–10 repository nguồn](#task-12-chọn-510-repository-nguồn)
   - [Task 1.3: Script crawl Issue + Pull Request](#task-13-script-crawl-issue--pull-request)
   - [Task 1.4: Pipeline làm sạch dữ liệu](#task-14-pipeline-làm-sạch-dữ-liệu)
   - [Task 1.5: Chuẩn hóa Schema Dataset](#task-15-chuẩn-hóa-schema-dataset)
   - [Task 1.6: Chốt số lượng & phân bố Benchmark](#task-16-chốt-số-lượng--phân-bố-benchmark)
   - [Task 1.7: Xây dựng Prompt v1 cho Analyzer](#task-17-xây-dựng-prompt-v1-cho-analyzer)
   - [Task 1.8: Kiểm thử Pilot 10 issues & Prompt v2](#task-18-kiểm-thử-pilot-10-issues--prompt-v2)
   - [Task 1.9: Xây dựng Batch LLM Pipeline](#task-19-xây-dựng-batch-llm-pipeline)
3. [HƯỚNG DẪN CHẠY TỪNG BƯỚC](#3-hướng-dẫn-thao-tác-ngoài-đời-thực-external-actions-guide)
   - [Bước 1: Thiết lập môi trường Python trên máy tính](#bước-1-thiết-lập-môi-trường-python-trên-máy-tính)
   - [Bước 2: Tạo GitHub Personal Access Token (PAT)](#bước-2-tạo-github-personal-access-token-pat)
   - [Bước 3: Cấu hình biến môi trường `.env`](#bước-3-cấu-hình-biến-môi-trường-env)
   - [Bước 4: Chạy Crawler thu thập dữ liệu thô](#bước-4-chạy-crawler-thu-thập-dữ-liệu-thô)
   - [Bước 5: Chạy làm sạch dữ liệu (Data Cleaning)](#bước-5-chạy-làm-sạch-dữ-liệu-data-cleaning)
   - [Bước 6: Lấy API Key LLM (OpenAI / Gemini / Claude)](#bước-6-lấy-api-key-llm)
   - [Bước 7: Chạy kiểm thử Pilot và đánh giá sai số](#bước-7-chạy-kiểm-thử-pilot-và-đánh-giá-sai-số)
   - [Bước 8: Chạy Batch LLM Analyzer toàn dataset](#bước-8-chạy-batch-llm-analyzer-toàn-dataset)
4. [QUY TRÌNH PHỐI HỢP LIÊN THÀNH VIÊN (TV1 ↔ TV2 ↔ TV3)](#4-quy-trình-phối-hợp-liên-thành-viên)
   - [Phối hợp với TV2 (MAS Engine Lead)](#phối-hợp-với-tv2-mas-engine-lead)
   - [Phối hợp với TV3 (Evaluation & Controller Lead)](#phối-hợp-với-tv3-evaluation--controller-lead)

---

## 1. TỔNG QUAN TIẾN ĐỘ 9 TASKS CỦA TV1

| Task | Tên nhiệm vụ | Deliverables / Artifacts | Trạng thái kỹ thuật |
|:---:|---|---|:---:|
| **1.1** | Viết tiêu chí lọc issue | [`docs/filter_rules.md`](file:///c:/Users/Admin/Desktop/DACN/Stage1/docs/filter_rules.md) | **ĐÃ HOÀN THÀNH** |
| **1.2** | Chọn 5–10 repository nguồn | [`docs/repository_list.md`](file:///c:/Users/Admin/Desktop/DACN/Stage1/docs/repository_list.md) | **ĐÃ HOÀN THÀNH** |
| **1.3** | Script crawl Issue + PR | [`scripts/github_api.py`](file:///c:/Users/Admin/Desktop/DACN/Stage1/scripts/github_api.py), [`scripts/crawl_dataset.py`](file:///c:/Users/Admin/Desktop/DACN/Stage1/scripts/crawl_dataset.py)... | **ĐÃ HOÀN THÀNH** |
| **1.4** | Làm sạch dataset | [`scripts/clean_dataset.py`](file:///c:/Users/Admin/Desktop/DACN/Stage1/scripts/clean_dataset.py) | **ĐÃ HOÀN THÀNH** |
| **1.5** | Chuẩn hóa schema dataset | [`docs/dataset_schema.md`](file:///c:/Users/Admin/Desktop/DACN/Stage1/docs/dataset_schema.md), cấu trúc `data/` | **ĐÃ HOÀN THÀNH** |
| **1.6** | Chốt số lượng benchmark | [`docs/data_collection_report.md`](file:///c:/Users/Admin/Desktop/DACN/Stage1/docs/data_collection_report.md) | **ĐÃ HOÀN THÀNH** |
| **1.7** | Viết Prompt v1 cho Analyzer | [`prompts/requirement_analyzer_v1.md`](file:///c:/Users/Admin/Desktop/DACN/Stage1/prompts/requirement_analyzer_v1.md) | **ĐÃ HOÀN THÀNH** |
| **1.8** | Test Prompt trên 10 issues | [`evaluation/pilot_10_results.json`](file:///c:/Users/Admin/Desktop/DACN/Stage1/evaluation/pilot_10_results.json), [`prompts/requirement_analyzer_v2.md`](file:///c:/Users/Admin/Desktop/DACN/Stage1/prompts/requirement_analyzer_v2.md) | **ĐÃ HOÀN THÀNH** |
| **1.9** | Xây dựng Batch LLM pipeline | [`analyzer/batch_runner.py`](file:///c:/Users/Admin/Desktop/DACN/Stage1/analyzer/batch_runner.py), [`analyzer/validator.py`](file:///c:/Users/Admin/Desktop/DACN/Stage1/analyzer/validator.py)... | **ĐÃ HOÀN THÀNH** |

---

## 2. CHI TIẾT TRIỂN KHAI TỪNG TASK

### Task 1.1: Viết tiêu chí lọc issue
- **Mục tiêu:** Xây dựng ranh giới rõ ràng để biết issue nào được đưa vào benchmark và issue nào bị loại, đảm bảo dữ liệu trải dài trên cả 4 trục $(C, T, S, I)$.
- **Tài liệu bàn giao:** [`docs/filter_rules.md`](file:///c:/Users/Admin/Desktop/DACN/Stage1/docs/filter_rules.md).
- **Quy tắc cốt lõi:**
  - *Inclusion:* Phải có thay đổi code thực tế ($\ge 3$ dòng), có Pull Request liên kết đã **MERGED**, issue text đủ ngữ cảnh ($\ge 20$ từ).
  - *Exclusion:* Loại bỏ spam, duplicate, bot dependency updates (`dependabot`), chỉ sửa docs (`README.md`, typo), PR chưa merge.
  - *Chống thiên lệch (No bias for difficulty):* Không chỉ chọn bài khó. Vẫn giữ các bug nhỏ sửa 1–2 dòng ($C=1, I=1$) để kiểm thử Collaboration Level tối thiểu L1.

---

### Task 1.2: Chọn 5–10 repository nguồn
- **Mục tiêu:** Tuyển chọn các dự án mã nguồn mở có độ hoàn thiện cao, kỷ luật review tốt, có mặt trong SWE-bench và đa dạng về ngôn ngữ / kiến trúc.
- **Tài liệu bàn giao:** [`docs/repository_list.md`](file:///c:/Users/Admin/Desktop/DACN/Stage1/docs/repository_list.md).
- **Danh sách 8 repository tuyển chọn:**
  1. `psf/requests` (Python - Networking / HTTP)
  2. `pallets/flask` (Python - Web WSGI Framework)
  3. `encode/django-rest-framework` (Python - Authentication, Permissions, API)
  4. `scikit-learn/scikit-learn` (Python - Machine Learning, Thuật toán, Toán học)
  5. `marshmallow-code/marshmallow` (Python - Data Validation / Serialization)
  6. `expressjs/express` (JavaScript / Node.js - Web Middleware)
  7. `gin-gonic/gin` (Go - Static typing, Concurrency engine)
  8. `elastic/elasticsearch` (Java - Phân tán, Enterprise architecture)

---

### Task 1.3: Script crawl Issue + Pull Request
- **Mục tiêu:** Xây dựng module tự động hóa thu thập dữ liệu qua GitHub API.
- **Các file mã nguồn:**
  - [`scripts/github_api.py`](file:///c:/Users/Admin/Desktop/DACN/Stage1/scripts/github_api.py): Quản lý GitHub API client, kiểm tra Rate Limit, tự động ngủ khi chạm ngưỡng giới hạn (403/429), exponential backoff retry.
  - [`scripts/file_parser.py`](file:///c:/Users/Admin/Desktop/DACN/Stage1/scripts/file_parser.py): Tách biệt file test vs source code vs doc files; tính toán additions, deletions và trích xuất patch code.
  - [`scripts/pr_parser.py`](file:///c:/Users/Admin/Desktop/DACN/Stage1/scripts/pr_parser.py): Phân giải liên kết Issue ↔ PR thông qua regex `fixes #123`, `closes #456` và metadata PR.
  - [`scripts/issue_crawler.py`](file:///c:/Users/Admin/Desktop/DACN/Stage1/scripts/issue_crawler.py): Ghép nối toàn bộ thông tin issue, PR đã merge và changed files.
  - [`scripts/crawl_dataset.py`](file:///c:/Users/Admin/Desktop/DACN/Stage1/scripts/crawl_dataset.py): Script CLI hỗ trợ tham số `--repos`, `--limit`, `--output-dir` và cờ `--mock` (để test offline không cần token).

---

### Task 1.4: Pipeline làm sạch dữ liệu
- **Mục tiêu:** Loại bỏ triệt để dữ liệu rác, duplicate, PR doc-only mà không gây ra hiện tượng lọc quá mức (over-cleaning).
- **Mã nguồn bàn giao:** [`scripts/clean_dataset.py`](file:///c:/Users/Admin/Desktop/DACN/Stage1/scripts/clean_dataset.py).
- **Cơ chế hoạt động:**
  - Lọc bỏ issue trùng lặp ID.
  - Lọc bỏ PR do bot tự động tạo.
  - Lọc bỏ issue quá ngắn hoặc tiêu đề vô nghĩa (`"bug"`, `"help"`).
  - Lọc bỏ PR có số dòng sửa đổi bằng 0 hoặc 100% là file Markdown/Docs.
  - In báo cáo tổng kết tỷ lệ Accept / Reject chi tiết theo từng lý do.

---

### Task 1.5: Chuẩn hóa Schema Dataset
- **Mục tiêu:** Cố định định dạng JSON cho toàn bộ dự án, phân tách rõ các giai đoạn dữ liệu, chuẩn hóa schema theo chuẩn SWE-bench mở rộng.
- **Tài liệu bàn giao:** [`docs/dataset_schema.md`](file:///c:/Users/Admin/Desktop/DACN/Stage1/docs/dataset_schema.md).
- **Trường dữ liệu nâng cao:**
  - `base_commit`: Mã SHA commit trước khi PR merge (chuẩn SWE-bench) ở cấp root và `linked_pr`.
  - `base_code`: Đoạn code nguyên bản trước khi merge trích xuất tự động từ git patch diff cho từng file thay đổi, giúp AI đối chiếu và chấm điểm rubric 4 trục $(C, T, S, I)$ chính xác nhất.
  - `base_file_url` & `base_commit_url`: Đường dẫn trực tiếp tới file và commit trên GitHub.
- **Phân định thư mục:**
  - `data/raw/`: Dữ liệu thô từ crawler.
  - `data/cleaned/`: Dữ liệu sạch đưa vào benchmark.
  - `data/annotations/`: Nhãn đánh giá thủ công của người (Ground Truth).
  - `data/analyzer_outputs/`: Kết quả Requirement Profile dự đoán bởi LLM.

---

### Task 1.6: Chốt số lượng & phân bố Benchmark
- **Mục tiêu:** Thống nhất điểm vênh giữa Checklist TV1 (60–100 issues) và Rubric Đề tài (150–200 issues), thiết lập tỷ lệ phân bố 4 trục.
- **Tài liệu bàn giao:** [`docs/data_collection_report.md`](file:///c:/Users/Admin/Desktop/DACN/Stage1/docs/data_collection_report.md).
- **Quyết định lộ trình:**
  - **Pilot Benchmark:** 10 issues (Đã xong ở Task 1.8).
  - **Core Benchmark:** **80 issues** (nằm trong dải 60–100 issues) làm tập chính cho Giai đoạn 1 và 2.
  - **Expanded Benchmark:** 150–200 issues (mở rộng ở Giai đoạn 3 khi train Learned Controller nếu cần).
  - **Giám sát phân bố:** Cân đối tỷ lệ điểm từ 1 đến 5 để tránh dataset bị lệch lệch tâm (skewed).

---

### Task 1.7: Xây dựng Prompt v1 cho Analyzer
- **Mục tiêu:** Thiết kế Prompt chuẩn hóa theo đúng Rubric 4 trục $R = (C, T, S, I)$, bắt buộc kèm trích dẫn bằng chứng (`evidence`), ép kiểu output JSON strictly.
- **Tài liệu bàn giao:** [`prompts/requirement_analyzer_v1.md`](file:///c:/Users/Admin/Desktop/DACN/Stage1/prompts/requirement_analyzer_v1.md).
- **Đặc tính kỹ thuật:**
  - Định nghĩa chi tiết ranh giới thang điểm 1 đến 5 cho từng trục.
  - Tích hợp 2 few-shot examples thể hiện sự khác biệt giữa bài toán cục bộ và bài toán bảo mật kiến trúc.

---

### Task 1.8: Kiểm thử Pilot 10 issues & Prompt v2
- **Mục tiêu:** Chạy thử Prompt v1 trên 10 issues tiêu biểu, so sánh với nhãn chuyên gia (**Human Ground Truth**), phân tích các điểm nhầm lẫn của LLM và nâng cấp Prompt v2.
- **Tài liệu bàn giao:**
  - Bộ dữ liệu kiểm thử pilot: [`evaluation/pilot_10_results.json`](file:///c:/Users/Admin/Desktop/DACN/Stage1/evaluation/pilot_10_results.json).
  - Báo cáo phân tích sai số: [`evaluation/prompt_error_analysis.md`](file:///c:/Users/Admin/Desktop/DACN/Stage1/evaluation/prompt_error_analysis.md).
  - Prompt v2 cải tiến: [`prompts/requirement_analyzer_v2.md`](file:///c:/Users/Admin/Desktop/DACN/Stage1/prompts/requirement_analyzer_v2.md).
- **Kết quả Pilot:** Đạt độ khớp hoàn toàn 80% (32/40 điểm trục), 100% nằm trong khoảng chấp nhận được ($\pm 1$). Đã triệt tiêu hiện tượng "Halo Effect" (nhầm lẫn Security với Complexity) và làm rõ ranh giới điểm Architecture Impact trong bản Prompt v2.

---

### Task 1.9: Xây dựng Batch LLM Pipeline
- **Mục tiêu:** Xây dựng hệ thống tự động hóa gọi LLM cho toàn bộ dataset có checkpoint, auto-retry, validation và resume an toàn khi gặp sự cố.
- **Các file mã nguồn:**
  - [`analyzer/llm_client.py`](file:///c:/Users/Admin/Desktop/DACN/Stage1/analyzer/llm_client.py): Đa kết nối (OpenAI, Gemini, Claude, Mock mode).
  - [`analyzer/prompt_builder.py`](file:///c:/Users/Admin/Desktop/DACN/Stage1/analyzer/prompt_builder.py): Ghép ngữ cảnh issue vào prompt template.
  - [`analyzer/output_parser.py`](file:///c:/Users/Admin/Desktop/DACN/Stage1/analyzer/output_parser.py): Trích xuất và bóc tách JSON an toàn từ phản hồi text.
  - [`analyzer/validator.py`](file:///c:/Users/Admin/Desktop/DACN/Stage1/analyzer/validator.py): Kiểm tra điểm số $1 \le score \le 5$, bắt buộc trường evidence.
  - [`analyzer/batch_runner.py`](file:///c:/Users/Admin/Desktop/DACN/Stage1/analyzer/batch_runner.py): Điều phối chạy hàng loạt, tự động lưu `data/analyzer_outputs/checkpoint.json` sau mỗi issue. Nếu mất mạng hoặc máy tắt, khi chạy lại sẽ tiếp tục từ issue đang dở mà không tốn tiền gọi lại các issue đã xong.

---

## 3. HƯỚNG DẪN CHẠY TỪNG BƯỚC

Phần này hướng dẫn bạn từng thao tác cụ thể bên ngoài hệ thống (trên terminal Windows PowerShell/CMD, trên trình duyệt web GitHub và cổng đăng ký API của các nhà cung cấp LLM).

---

### Bước 1: Thiết lập môi trường Python trên máy tính

Mở **PowerShell** hoặc **Command Prompt** tại thư mục dự án `c:\Users\Admin\Desktop\DACN\Stage1`:

```powershell
# 1. Di chuyển vào thư mục Stage1
cd c:\Users\Admin\Desktop\DACN\Stage1

# 2. Tạo môi trường ảo Python (Virtual Environment)
python -m venv venv

# 3. Kích hoạt môi trường ảo
# Nếu dùng PowerShell:
.\venv\Scripts\Activate.ps1
# (Nếu PowerShell báo lỗi Execution Policy, chạy lệnh: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass rồi activate lại)
# Nếu dùng Command Prompt (CMD):
venv\Scripts\activate.bat

# 4. Cài đặt các thư viện phụ thuộc
pip install -r requirements.txt
```

---

### Bước 2: Tạo GitHub Personal Access Token (PAT)

Để crawl được dữ liệu từ GitHub mà không bị giới hạn 60 requests/giờ (Token giúp tăng lên **5,000 requests/giờ**):

1. Truy cập trình duyệt web: [https://github.com/settings/tokens](https://github.com/settings/tokens)
2. Đăng nhập tài khoản GitHub của bạn.
3. Chọn **Generate new token** $\rightarrow$ **Generate new token (classic)**.
4. Tại ô **Note**: Đặt tên gợi nhớ, ví dụ: `RAAC_Crawler_Token`.
5. Tại mục **Expiration**: Chọn `30 days` hoặc `90 days`.
6. Tại mục **Select scopes**: Tích chọn quyền:
   - `public_repo` (Truy cập các repository công khai).
   - `read:org` (Đọc thông tin tổ chức nếu cần).
7. Cuộn xuống dưới cùng và bấm nút xanh **Generate token**.
8. **Sao chép mã token** hiển thị trên màn hình (dạng `ghp_xxxxxxxxxxxxxxxxxxxx`). *Lưu ý: Mã này chỉ hiện 1 lần duy nhất, hãy lưu vào nơi an toàn.*

---

### Bước 3: Cấu hình biến môi trường `.env`

Tại thư mục `Stage1`, tạo một tệp có tên là `.env` (hoặc sao chép từ `.env.example`):

```powershell
copy .env.example .env
```

Mở tệp `.env` bằng trình soạn thảo (Notepad hoặc VS Code) và dán token vừa tạo:

```env
# GitHub Token cho Crawler
GITHUB_TOKEN=ghp_chuỗi_token_của_bạn_ở_đây

# Nhà cung cấp LLM mặc định: "mock", "openai", hoặc "gemini"
LLM_PROVIDER=mock

# Nếu dùng OpenAI (GPT-4o / GPT-4o-mini)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Nếu dùng Google Gemini (Gemini 1.5 Flash / Pro)
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-1.5-flash
```

---

### Bước 4: Chạy Crawler thu thập dữ liệu thô

Bạn có hai lựa chọn chạy:

#### Lựa chọn 4A: Chạy thật với GitHub API (Yêu cầu đã có Token)
Chạy crawl 10–30 issues từ các repo SWE-bench mục tiêu:

```powershell
# Crawl 3 repository tiêu biểu (requests, flask, django-rest-framework)
python scripts/crawl_dataset.py --repos psf/requests pallets/flask encode/django-rest-framework --limit 15 --output-dir data/raw
```
- Dữ liệu sẽ được lưu tại: `data/raw/psf_requests_issues.json`, `data/raw/all_crawled_raw.json`.
- Crawler tự động hiển thị số lượng request còn lại trong hạn mức 5000 requests/giờ.

#### Lựa chọn 4B: Chạy thử nghiệm Mock (Không cần token, không cần mạng)
Nếu bạn chưa kịp tạo GitHub token, hệ thống hỗ trợ sẵn chế độ `--mock` tạo ngay bộ dữ liệu mẫu chuẩn:

```powershell
python scripts/crawl_dataset.py --mock
```
- Dữ liệu mẫu sẽ tạo tại: `data/raw/mock_crawled_issues.json`.

---

### Bước 5: Chạy làm sạch dữ liệu (Data Cleaning)

Sau khi có dữ liệu thô trong `data/raw/`, chạy script làm sạch để loại bỏ spam, bot, và các PR tài liệu:

```powershell
# Chạy lọc và xuất ra file cleaned_benchmark.json
python scripts/clean_dataset.py --input data/raw/all_crawled_raw.json --output data/cleaned/cleaned_benchmark.json
```

Terminal sẽ in ra bảng thống kê:
- Tổng số issues đưa vào.
- Số issues đạt chuẩn (Kept).
- Số issues bị loại theo từng phân loại (Duplicate, Unmerged PR, Bot, Short/Spam, Doc/Comment-only).

> **Lưu ý quan trọng về tính tái lập (Reproducibility):**
> - **Tuyệt đối KHÔNG xóa tay trực tiếp trong file `cleaned_benchmark.json`**: Mọi thao tác chỉnh sửa tay trực tiếp vào file kết quả sẽ bị ghi đè khi pipeline chạy lại, vi phạm nguyên tắc chuẩn của nghiên cứu khoa học và benchmark SWE-bench.
> - Hệ thống làm sạch đã được nâng cấp bộ phân tích diff tự động (`is_comment_or_doc_patch`): tự động phát hiện và loại bỏ các PR chỉ sửa docstring, comment `#`, hoặc các tag tài liệu (`:param`, `@param`) ngay cả khi chúng nằm bên trong các file mã nguồn `.py` (ví dụ: trường hợp `psf_requests_6813`).

---

### Bước 5.1: Quy trình Kiểm tra Thủ công (Human Spot-check) & Loại trừ Ngoại lệ (Blacklist)

Bạn **không cần** phải duyệt thủ công 100% dataset (vừa tốn công vừa mang tính chủ quan). Thay vào đó, áp dụng quy trình kiểm định mẫu khoa học (**Audit Spot-check**):

#### 1. Thao tác lấy mẫu kiểm định (10–20 issues):
- Mở ngẫu nhiên 10–20 issue trong file `data/cleaned/cleaned_benchmark.json` (có thể kết hợp trực tiếp với 10 issue Pilot ở Bước 7).
- Kiểm tra nhanh theo **Checklist 3 câu hỏi**:
  1. **Ngữ cảnh (Context):** Issue title và body có đủ thông tin kỹ thuật để hiểu lỗi/yêu cầu không?
  2. **Thay đổi thực chất (Code Diff):** Vào link PR, xem tab *Files changed*, xác nhận PR có sửa đổi logic thực thi hay chỉ là comment/formatting sót lại?
  3. **Độ đa dạng:** Issue này thuộc bài dễ ($C=1, I=1$) hay bài phức tạp ($C \ge 3, I \ge 3$)?

#### 2. Thao tác xử lý nếu phát hiện Issue không đạt chuẩn (Manual Blacklist):
Nếu phát hiện một issue cá biệt lọt qua bộ lọc tự động, **thao tác tay duy nhất bạn cần làm** là mở file cấu hình:

```text
data/blacklist_issues.json
```

Thêm ID của issue đó kèm lý do loại trừ:

```json
{
  "_description": "Danh sách các Issue ID bị loại trừ thủ công kèm lý do",
  "psf_requests_xxxx": "Mô tả quá mơ hồ sau khi con người thẩm định",
  "pallets_flask_yyyy": "PR chỉ đổi định dạng format khoảng trắng"
}
```

Sau đó chạy lại lệnh `python scripts/clean_dataset.py`. Script sẽ tự động loại bỏ issue này và ghi nhận vào danh mục `Manual Blacklist` trong báo cáo.

---

### Bước 5.2: Kiểm tra Phân bố & Chống Thiên Lệch Dataset (Anti-bias Audit)

Để đảm bảo dataset phản ánh đúng thực tế khách quan và đáp ứng tiêu chí **"Chống thiên lệch (Anti-bias)"** trong Rubric Đồ án (không chỉ toàn bài khó, không bị độc quyền bởi 1 repo, cân bằng testability):

Chạy công cụ kiểm định phân bố tự động:

```powershell
python scripts/check_dataset_bias.py --input data/cleaned/cleaned_benchmark.json --report docs/dataset_bias_report.md
```

Công cụ sẽ phân tích và in ra bảng tổng kết 4 chiều:
1. **Phân bố Repository:** Đảm bảo mỗi repo chiếm từ 20%–40%, không repo nào độc quyền > 50%.
2. **Phân bố Kích thước Mã nguồn (LOC Bins):**
   - **Micro (1–5 LOC):** Bug nhỏ sửa cục bộ ($C=1, I=1$) để kiểm thử Collaboration Level tối thiểu L1.
   - **Small (6–20 LOC):** Tinh chỉnh logic đơn lẻ ($C=2$).
   - **Medium (21–100 LOC):** Tính năng nhỏ, sửa nhiều hàm ($C=3, I=2..3$).
   - **Large (>100 LOC):** Refactor, kiến trúc sâu ($C=4..5, I=4..5$) để kiểm thử phân hệ L3/L4.
3. **Cân bằng Testability:** Giữ tỷ lệ hài hòa giữa issue có unit test và issue không có test (phụ thuộc môi trường/manual test) để đánh giá trục $T$.
4. **Báo cáo chi tiết:** Tự động xuất file markdown tại `docs/dataset_bias_report.md` sẵn sàng dùng làm minh chứng đưa vào báo cáo nghiệm thu Giai đoạn 1.

---

### Bước 6: Lấy API Key LLM

Để chạy Requirement Analyzer bằng mô hình AI thực tế:

#### Nếu chọn OpenAI:
1. Đăng nhập [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Bấm **Create new secret key**, copy key bắt đầu bằng `sk-...`
3. Dán vào `OPENAI_API_KEY` trong tệp `.env`.

#### Nếu chọn Google Gemini (Rất tiết kiệm chi phí / có gói miễn phí):
1. Đăng nhập [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Bấm **Create API key**.
3. Copy key và dán vào `GEMINI_API_KEY` trong tệp `.env`.

---

### Bước 7: Chạy kiểm thử Pilot và đánh giá sai số

Để đối chiếu độ chính xác của Prompt trên 10 issues pilot:
1. Mở file `evaluation/pilot_10_results.json` để xem kết quả đối chiếu giữa chuyên gia và AI.
2. Đọc báo cáo phân tích lỗi tại `evaluation/prompt_error_analysis.md`.
3. Nhận biết các điểm cải tiến đã được đưa vào `prompts/requirement_analyzer_v2.md`.

---

### Bước 8: Chạy Batch LLM Analyzer toàn dataset

Chạy tiến trình phân tích tự động cho toàn bộ tập benchmark đã làm sạch:

#### Chạy chế độ Mock (Để kiểm tra luồng hoạt động, không mất phí):
```powershell
python analyzer/batch_runner.py --provider mock --version v2
```

#### Chạy thật với OpenAI hoặc Gemini:
```powershell
# Chạy với OpenAI (gpt-4o-mini)
python analyzer/batch_runner.py --provider openai --version v2 --input data/cleaned/cleaned_benchmark.json

# Hoặc chạy với Gemini (gemini-1.5-flash)
python analyzer/batch_runner.py --provider gemini --version v2 --input data/cleaned/cleaned_benchmark.json
```

#### Các tùy chọn hữu ích khi chạy batch:
- Giới hạn số issue chạy thử: `--limit 5`
- Xóa tiến trình cũ chạy lại từ đầu: `--clean-checkpoint`
- **Cơ chế phục hồi tự động:** Nếu đang chạy mà máy tính mất mạng hoặc bạn bấm `Ctrl + C`, bạn chỉ cần gõ lại lệnh trên mà không thêm `--clean-checkpoint`. Script sẽ tự động đọc `data/analyzer_outputs/checkpoint.json` và tiếp tục chạy từ vị trí bị ngắt quãng.

---

## 4. QUY TRÌNH PHỐI HỢP LIÊN THÀNH VIÊN (INTERFACE CONTRACTS)

### Phối hợp với TV2 (MAS Engine Lead)
- **Điểm giao tiếp dữ liệu:** TV1 cung cấp đầu ra là Requirement Profile $\mathbf{R} = (C, T, S, I)$ lưu tại `data/analyzer_outputs/` hoặc hàm gọi trực tiếp từ `analyzer/batch_runner.py`.
- **Cách TV2 sử dụng:**
  - Ở **L1 (Fixed Workflow):** TV2 lấy thông tin issue thô từ `data/cleaned/cleaned_benchmark.json` để chạy thử pipeline tuần tự 5 role (Analyst $\rightarrow$ Planner $\rightarrow$ Coder $\rightarrow$ Tester $\rightarrow$ Reviewer).
  - Ở **L2 – L4 (Adaptive Ladder):** TV2 dùng trực tiếp vector $R = (C, T, S, I)$ làm đầu vào cho **Adaptivity Controller** để quyết định cấu hình agent (bật/tắt vai trò Security Agent khi $S \ge 4$, tăng số vòng lặp review khi $C \ge 4$, hoặc thêm QA verification loop khi $T \ge 4$).

### Phối hợp với TV3 (Evaluation & Controller Lead)
- **Điểm giao tiếp dữ liệu:**
  1. TV1 xuất file `data/cleaned/cleaned_benchmark.json` chuyển cho TV3.
  2. TV3 dùng file này để import vào Google Sheets / Label Studio phục vụ việc chấm nhãn độc lập giữa các thành viên (Task 3.1–3.4).
  3. TV1 cung cấp kết quả dự đoán của mô hình từ `data/analyzer_outputs/`.
  4. TV3 chạy script tính độ đồng thuận liên đánh giá (**Weighted Cohen's Kappa** giữa 2 người, mục tiêu $\kappa_w \ge 0.70$) và tính hệ số tương quan (**Spearman / Pearson correlation**) giữa nhãn người và điểm số do TV1 Analyzer sinh ra.
  5. Nếu TV3 phát hiện trục nào có độ tương quan thấp (ví dụ trục Testability), TV1 sẽ dựa vào phản hồi đó để tinh chỉnh Prompt v3.

---
*Tài liệu này được biên soạn và chuẩn hóa đầy đủ theo toàn bộ yêu cầu của TV1 trong Giai đoạn 1 đề tài RAAC.*