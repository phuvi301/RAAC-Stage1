# Đặc Tả Schema Dữ Liệu Benchmark (Dataset Schema)
## Dự án RAAC – Requirement-Aware Adaptive Collaboration

Tài liệu này quy định cấu trúc tổ chức tệp và cấu trúc JSON chuẩn (Standard JSON Schemas) cho toàn bộ vòng đời dữ liệu trong Giai đoạn 1 của RAAC.

---

## 1. Nguyên tắc Tổ chức Thư mục Dữ liệu

Để tránh nhầm lẫn giữa dữ liệu thô (raw), dữ liệu đã làm sạch (cleaned), nhãn của chuyên gia người (human annotations) và kết quả dự đoán của mô hình (LLM predictions), hệ thống phân tách nghiêm ngặt thành 4 thư mục chuyên biệt:

```text
data/
├── raw/                 # Dữ liệu thô crawl trực tiếp từ GitHub API
│   ├── psf_requests_issues.json
│   ├── pallets_flask_issues.json
│   └── all_crawled_raw.json
│
├── cleaned/             # Dữ liệu đã lọc theo filter_rules.md, sẵn sàng cho annotation & analyzer
│   ├── cleaned_benchmark.json
│   └── pilot_10_samples.json
│
├── annotations/         # Nhãn thủ công của chuyên gia (TV3 / Human Annotators)
│   ├── annotator_1.json
│   ├── annotator_2.json
│   └── ground_truth.json
│
└── analyzer_outputs/    # Kết quả Requirement Profile sinh bởi Requirement Analyzer LLM
    ├── run_gpt4o_v1_20260920.json
    ├── run_gemini_v1_20260920.json
    └── checkpoint.json
```

---

## 2. Schema Dữ liệu Đã Làm Sạch (Cleaned Benchmark Schema)

Tệp `data/cleaned/cleaned_benchmark.json` được phân nhóm theo từng repository và lưu các issue chuẩn:

```json
{
  "dataset_version": "v1-genuine-hard",
  "total_repos": 3,
  "total_issues": 104,
  "repos": [
    {
      "repo": "psf/requests",
      "repo_url": "https://github.com/psf/requests",
      "issues": [
        {
          "id": "psf__requests-7432",
          "url": "https://github.com/psf/requests/pull/7433",
          "title": "`prepare_body` stream detection regression",
          "body": "...",
          "base_commit": "0b401c76b6e80a4eecf3c690085b2553f6e261ca"
        }
      ]
    }
  ]
}
```
---

## 3. Schema Kết Quả Requirement Analyzer (LLM Output Schema)

Kết quả sinh bởi Requirement Analyzer tuân thủ nghiêm ngặt vector $R = (C, T, S, I) \in \{1, 2, 3, 4, 5\}^4$, trong đó mỗi trục bắt buộc phải đi kèm trích dẫn chứng cứ cụ thể (`evidence`):

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "RequirementAnalyzerPrediction",
  "type": "object",
  "required": ["issue_id", "model", "prompt_version", "profile", "metadata"],
  "properties": {
    "issue_id": { "type": "string" },
    "model": { "type": "string", "example": "gpt-4o-mini" },
    "prompt_version": { "type": "string", "example": "v1.0" },
    "profile": {
      "type": "object",
      "required": ["complexity", "testability", "security_sensitivity", "architecture_impact"],
      "properties": {
        "complexity": {
          "type": "object",
          "required": ["score", "evidence"],
          "properties": {
            "score": { "type": "integer", "minimum": 1, "maximum": 5 },
            "evidence": { "type": "string", "minLength": 10 }
          }
        },
        "testability": {
          "type": "object",
          "required": ["score", "evidence"],
          "properties": {
            "score": { "type": "integer", "minimum": 1, "maximum": 5 },
            "evidence": { "type": "string", "minLength": 10 }
          }
        },
        "security_sensitivity": {
          "type": "object",
          "required": ["score", "evidence"],
          "properties": {
            "score": { "type": "integer", "minimum": 1, "maximum": 5 },
            "evidence": { "type": "string", "minLength": 10 }
          }
        },
        "architecture_impact": {
          "type": "object",
          "required": ["score", "evidence"],
          "properties": {
            "score": { "type": "integer", "minimum": 1, "maximum": 5 },
            "evidence": { "type": "string", "minLength": 10 }
          }
        }
      }
    },
    "metadata": {
      "type": "object",
      "required": ["timestamp", "latency_ms", "status"],
      "properties": {
        "timestamp": { "type": "string", "format": "date-time" },
        "tokens_prompt": { "type": "integer" },
        "tokens_completion": { "type": "integer" },
        "latency_ms": { "type": "integer" },
        "status": { "type": "string", "enum": ["success", "error"] },
        "error_message": { "type": ["string", "null"] }
      }
    }
  }
}
```

---

## 4. Schema Nhãn Chuyên Gia & Ground Truth (Human Annotation Schema)

Lưu tại `data/annotations/ground_truth.json`:

```json
{
  "issue_id": "psf_requests_4175",
  "annotators": ["TV1_Lead", "TV3_Lead"],
  "scores": {
    "complexity": 2,
    "testability": 2,
    "security_sensitivity": 1,
    "architecture_impact": 1
  },
  "consensus_notes": "Thay đổi cục bộ trong Session.send, sửa copy headers, có unit test rõ ràng.",
  "inter_rater_discrepancy": 0
}
```
