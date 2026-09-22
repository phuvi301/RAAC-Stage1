"""
Module: validator.py
Xác thực tính hợp lệ của Requirement Profile sinh ra bởi LLM:
- Kiểm tra đủ 4 trục: Complexity, Testability, Security Sensitivity, Architecture Impact.
- Kiểm tra điểm số là số nguyên trong khoảng [1, 5].
- Kiểm tra có trường evidence đầy đủ và không rỗng.
"""

from typing import Dict, Any, List, Tuple


class ProfileValidator:
    REQUIRED_AXES = [
        "complexity",
        "testability",
        "security_sensitivity",
        "architecture_impact"
    ]

    @classmethod
    def validate(cls, profile_dict: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Kiểm tra tính hợp lệ của Requirement Profile.
        Trả về (is_valid, list_of_error_messages).
        """
        errors = []

        if not isinstance(profile_dict, dict):
            return False, ["Output không phải là một JSON object/dictionary."]

        for axis in cls.REQUIRED_AXES:
            if axis not in profile_dict:
                errors.append(f"Thiếu trục đánh giá bắt buộc: '{axis}'")
                continue

            axis_data = profile_dict[axis]
            if not isinstance(axis_data, dict):
                errors.append(f"Dữ liệu của trục '{axis}' phải là dictionary chứa 'score' và 'evidence'.")
                continue

            # Kiểm tra score
            score = axis_data.get("score")
            if score is None:
                errors.append(f"Trục '{axis}' thiếu trường 'score'.")
            elif not isinstance(score, int) or score < 1 or score > 5:
                # Xử lý trường hợp LLM trả về số dạng chuỗi hoặc float tròn
                try:
                    score_int = int(score)
                    if 1 <= score_int <= 5:
                        axis_data["score"] = score_int
                    else:
                        errors.append(f"Trục '{axis}' có score={score} nằm ngoài khoảng hợp lệ [1, 5].")
                except (ValueError, TypeError):
                    errors.append(f"Trục '{axis}' có score={score} không phải số nguyên [1, 5].")

            # Kiểm tra evidence
            evidence = axis_data.get("evidence")
            if not evidence or not isinstance(evidence, str) or len(evidence.strip()) < 5:
                errors.append(f"Trục '{axis}' thiếu trích dẫn bằng chứng ('evidence' tối thiểu 5 ký tự).")

        is_valid = len(errors) == 0
        return is_valid, errors
