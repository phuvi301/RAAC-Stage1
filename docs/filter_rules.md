# Tiêu chí Lọc Issue cho Benchmark Dataset (Filter Rules)
## Dự án RAAC – Requirement-Aware Adaptive Collaboration

Tài liệu này xác lập bộ tiêu chí chuẩn hóa để quyết định một **GitHub Issue** có đủ điều kiện để đưa vào tập dữ liệu benchmark phục vụ đánh giá **Requirement Analyzer** và **Adaptivity Controller** trong nghiên cứu RAAC hay không.

---

## 1. Mục tiêu và Nguyên tắc Cốt lõi

Dataset của RAAC phục vụ việc nghiên cứu câu hỏi:
> *Khi nào, tại sao và ở mức độ nào các phần mềm agents nên cộng tác với nhau để giải quyết một software requirement?*

Vì vậy, tiêu chí lọc **tuyệt đối không được thiên vị** hoặc chỉ chọn các issue "khó" (high complexity / high architecture impact). Dataset bắt buộc phải trải rộng trên toàn bộ không gian 4 chiều $R = (C, T, S, I) \in [1, 5]^4$:
- Từ các task đơn giản, thay đổi cục bộ ($C=1, I=1$) cho đến các bài toán phân tán, thay đổi kiến trúc sâu rộng ($C=5, I=5$).
- Từ các task cực kỳ dễ kiểm thử tự động ($T=1$) cho đến các task phụ thuộc môi trường, non-deterministic hoặc bất khả thi kiểm thử tự động ($T=5$).
- Từ các task không liên quan bảo mật ($S=1$) cho đến các lỗ hổng nghiêm trọng về xác thực, phân quyền, rò rỉ dữ liệu ($S=5$).

---

## 2. Tiêu chí Đưa vào (Inclusion Criteria)

Một issue được chấp nhận vào dataset nếu thỏa mãn **tất cả** các điều kiện sau:

1. **Bản chất kỹ thuật (Technical Relevance):**
   - Là một yêu cầu phần mềm thực tế: sửa lỗi (bug fix), thêm tính năng mới (feature request), tái cấu trúc (refactoring) hoặc tối ưu hóa hiệu năng (performance enhancement).
   - Yêu cầu thay đổi hành vi thực thi, luồng logic hoặc cấu trúc mã nguồn của repository.
2. **Có liên kết trực tiếp với Pull Request thành công (Linked Merged PR):**
   - Phải có ít nhất một Pull Request (PR) liên kết trực tiếp và đã được **MERGED** vào nhánh chính (main/master).
   - PR này phải là giải pháp thực tế giải quyết requirement được mô tả trong issue (được xác nhận qua keyword đóng issue: `closes #123`, `fixes #123`, `resolves #123` hoặc liên kết chính thức trong timeline sự kiện của GitHub).
3. **Có thay đổi mã nguồn thực chất (Substantive Code Changes):**
   - PR liên kết phải có thay đổi trong các file source code thực thi của dự án (ví dụ: `.py`, `.ts`, `.js`, `.java`, `.go`, `.rs`, `.c`, `.cpp`).
   - Tổng số dòng thay đổi (additions + deletions) tối thiểu từ 3 dòng trở lên và không đơn thuần là thay đổi comment hoặc format code.
4. **Độ đầy đủ thông tin (Information Completeness):**
   - Tiêu đề (title) và nội dung (body) của issue phải có độ dài tối thiểu từ **20 từ** hoặc mô tả đủ: bối cảnh xảy ra lỗi, hành vi mong muốn, hoặc mô tả tính năng cần thêm.
   - Requirement Analyzer có đủ ngữ cảnh để hiểu mục tiêu mà không cần phải đoán mò do thiếu thông tin.
5. **Khả năng xác định Test (Test Trackability):**
   - Ưu tiên cao các PR có kèm theo file test hoặc sửa đổi test suite (`tests/`, `*_test.py`, `*Test.java`, `.spec.ts`), phục vụ việc đo lường khách quan cho trục Testability ($T$) và nghiệm thu chất lượng sau này.

---

## 3. Tiêu chí Loại trừ (Exclusion Criteria)

Loại bỏ ngay lập tức nếu issue/PR rơi vào bất kỳ trường hợp nào sau đây:

1. **Rác và trùng lặp (Spam & Duplicate):**
   - Các issue bị đánh nhãn `invalid`, `wontfix`, `duplicate`, hoặc do bot spam.
   - Các issue trùng lặp cùng một lỗi đã được xử lý ở issue khác.
2. **Thiếu thông tin nghiêm trọng (Severely Under-specified):**
   - Issue chỉ có vài từ chung chung không có mô tả kỹ thuật (ví dụ: *"Bug"*, *"App crashes"*, *"Please help fix"*).
   - Issue mà toàn bộ mô tả chỉ là ảnh chụp màn hình không có văn bản hoặc link ngoại vi đã hỏng (broken link).
3. **Thay đổi chỉ mang tính tài liệu hoặc hình thức (Doc-only & Cosmetic Changes):**
   - PR chỉ sửa đổi tệp tài liệu: `README.md`, `CHANGELOG.md`, `LICENSE`, `docs/*.rst`.
   - PR chỉ sửa lỗi chính tả (typo fix), dịch ngôn ngữ hiển thị (i18n string text thuần túy), hoặc format khoảng trắng (linter/prettier reformat).
4. **Không có thay đổi mã nguồn (Zero Code Change):**
   - Issue được giải quyết chỉ bằng cách đóng (closed by maintainer) do thảo luận xong, không phát sinh commit nào.
   - PR giải quyết đóng issue chỉ bằng việc xóa file rác, đổi tên file mà không đổi logic.
5. **Cập nhật tự động của Bot (Automated Dependency Updates):**
   - Các PR/Issue tạo tự động bởi Dependabot, Renovate bot chỉ để nâng cấp phiên bản dependency (ví dụ: `Bump lodash from 4.1.0 to 4.1.1`) mà không đi kèm việc xử lý breaking change phức tạp.
6. **Mất liên kết PR / PR bị từ chối (Unmerged or Abandoned PR):**
   - PR liên kết bị đóng mà không merge (`state: closed, merged: false`).
   - Issue đóng nhưng không thể truy xuất được PR giải quyết cụ thể.

---

## 4. Quy tắc Xử lý các Trường hợp Ngoại lệ (Edge Cases)

| Tình huống ngoại lệ (Edge Case) | Quy tắc xử lý | Giải thích |
|---|---|---|
| **Một Issue có nhiều PR giải quyết** | Chọn PR **cuối cùng được merged** hoặc PR tổng hợp mang lại giải pháp hoàn thiện nhất. | Đảm bảo tính nhất quán của ground truth về code diff. |
| **Một PR giải quyết nhiều Issue** | Chỉ giữ Issue đại diện rõ ràng nhất cho khối lượng công việc chính của PR; loại các issue phụ thuộc thứ yếu. | Tránh hiện tượng trùng lặp code changes cho nhiều requirement khác nhau trong benchmark. |
| **PR dạng Squash & Merge** | Chấp nhận bình thường. Lấy commit tổng hợp sau squash hoặc lấy diff qua GitHub Pull Request Files API. | GitHub API vẫn cung cấp đầy đủ danh sách changed files và patch tổng thể của PR. |
| **PR có revert commit** | Chỉ lấy diff ròng (net diff) cuối cùng giữa base branch và head branch của PR khi merge. | Phản ánh chính xác kết quả thực sự đưa vào codebase. |
| **Issue không có test trong PR** | **VẪN GIỮ** nếu issue thỏa mãn các tiêu chí khác. Đánh dấu cờ `has_test = False`. | Tránh thiên lệch sang chỉ lấy các repo/issue kỷ luật cao. Điểm Testability ($T$) của issue này sẽ được đánh giá dựa trên độ khó để viết test cho nó. |
| **PR vừa sửa code vừa sửa documentation** | **GIỮ** nếu phần code change là trọng tâm và giải quyết trực tiếp logic của issue. Bóc tách danh sách file test/code riêng biệt khỏi doc files. | Đa số PR thực tế của kỹ sư đều có cập nhật tài liệu đi kèm. |

---

## 5. Ví dụ Minh họa Cụ thể

### 5.1. Ví dụ Issue ĐƯỢC GIỮ (ACCEPT)

#### Ví dụ 1 (Độ phức tạp trung bình, có test)
- **Repository:** `psf/requests`
- **Issue #4175:** *"Session.send should not mutate request headers when prepared request is passed"*
- **Mô tả:** Trình bày chi tiết luồng khi user truyền một `PreparedRequest` tùy chỉnh vào `Session.send()`, phương thức tự động ghi đè hoặc mutate các headers ban đầu khiến retry request bị lỗi. Kèm snippet code tái hiện.
- **Linked PR:** #4182 (Merged, 1 file code `sessions.py`, 1 file test `test_requests.py`, +15 dòng, -4 dòng).
- **Quyết định:** **ACCEPT**.
- **Lý do:** Requirement rõ ràng, có code reproduction, có code change logic thực tế, có unit test đi kèm xác thực.

#### Ví dụ 2 (Đơn giản, cục bộ - low C, low I)
- **Repository:** `pallets/flask`
- **Issue #3922:** *"url_for raises KeyError when endpoint not found with subdomains"*
- **Mô tả:** Mô tả rõ lỗi ném ngoại lệ sai khi gọi `url_for` trên blueprint có subdomain rỗng, kèm stack trace.
- **Linked PR:** #3925 (Merged, sửa 5 dòng trong `helpers.py`, thêm 1 test case trong `test_helpers.py`).
- **Quyết định:** **ACCEPT**.
- **Lý do:** Giúp cân bằng phổ điểm cho các requirement nhỏ ($C=1..2, I=1$), cần thiết cho phân hệ cộng tác tối thiểu L1.

#### Ví dụ 3 (Tác động kiến trúc và bảo mật - high S, high I)
- **Repository:** `encode/django-rest-framework`
- **Issue #5832:** *"CVE check: Session authentication CSRF token disclosure on API view exceptions"*
- **Mô tả:** Phân tích chi tiết rủi ro bảo mật CSRF khi view API trả về lỗi ngoại lệ mà không xóa session cookie, ảnh hưởng đến tầng middleware bảo mật và cơ chế xác thực toàn hệ thống.
- **Linked PR:** #5835 (Merged, tác động đến middleware, authentication contracts và test suites bảo mật).
- **Quyết định:** **ACCEPT**.
- **Lý do:** Đại diện xuất sắc cho bài toán đòi hỏi bảo mật cao ($S=4..5$) và thay đổi kiến trúc ranh giới ($I=4..5$).

---

### 5.2. Ví dụ Issue BỊ LOẠI (REJECT)

#### Ví dụ 1: Không có mô tả / Mơ hồ
- **Repository:** `psf/requests`
- **Issue #7602:** *"Test issue"* (Không ghi link nào, trang nào).
- **Quyết định:** **REJECT**.
- **Lý do:** Vi phạm tiêu chí 4 (Information Completeness), mơ hồ nghiêm trọng.

#### Ví dụ 2: Documentation-only
- **Repository:** `encode/django-rest-framework`
- **Issue #6885:** *"Versioning docs kind of outdated"*
- **Linked PR #7043:** *"replaced url() with re_path() in Versioning docs"*
- **Quyết định:** **REJECT**.
- **Lý do:** Vi phạm tiêu chí 3 (Substantive Code Changes), thuần tài liệu, không có giá trị đo lường năng lực lập trình của software agents.

#### Ví dụ 3: Bot update thuần túy
- **Repository:** `pallets/flask`
- **PR / Issue #3925:** *"Bump tox from 3.21.4 to 3.22.0"* by `dependabot-preview`
- **Quyết định:** **REJECT**.
- **Lý do:** Vi phạm tiêu chí loại trừ 5. Không yêu cầu phân tích requirement hay ra quyết định cộng tác kiến trúc.
