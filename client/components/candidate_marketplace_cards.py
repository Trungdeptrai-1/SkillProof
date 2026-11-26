"""Presentation-only cards for candidate marketplace lists.

Data is read from controller outputs. Never invent badges, salary, or contact details.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


STATUS_LABELS = {
    "submitted": "Đã gửi hồ sơ",
    "reviewing": "Đang xem xét",
    "shortlisted": "Đã qua sơ tuyển",
    "assessment": "Đang đánh giá",
    "interview": "Đang phỏng vấn",
    "offered": "Đã nhận đề nghị",
    "rejected": "Không phù hợp",
    "withdrawn": "Đã rút đơn",
    "published": "Đang tuyển",
    "draft": "Bản nháp",
    "closed": "Đã đóng",
    "pending": "Đang chờ phản hồi",
    "accepted": "Đã chấp nhận",
    "declined": "Đã từ chối",
    "cancelled": "Đã hủy",
}
def status_label(value: object) -> str:
    if value is None or str(value).strip() == "":
        return "Chưa cập nhật"
    return STATUS_LABELS.get(str(value), str(value))


def list_card(row: dict, kind: str) -> QWidget:
    """A realistic content card with no fabricated personal/job data."""
    root = QFrame()
    root.setObjectName("CandidateListCard")
    root.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    outer = QHBoxLayout(root)
    outer.setContentsMargins(18, 14, 18, 14)
    outer.setSpacing(12)
    symbol = {"applications": "▣", "saved": "★", "invites": "✉"}.get(kind, "▤")
    marker = QLabel(symbol)
    marker.setObjectName("CandidateCardMarker")
    marker.setFixedSize(42, 42)
    marker.setAlignment(Qt.AlignmentFlag.AlignCenter)
    outer.addWidget(marker, 0, Qt.AlignmentFlag.AlignTop)

    main = QVBoxLayout()
    main.setSpacing(5)
    title = QLabel(str(row.get("title") or row.get("job_title") or "Vị trí tuyển dụng"))
    title.setObjectName("CandidateCardTitle")
    title.setWordWrap(True)
    main.addWidget(title)
    company = QLabel(str(row.get("company_name") or "Doanh nghiệp"))
    company.setObjectName("CandidateCardCompany")
    company.setWordWrap(True)
    main.addWidget(company)

    subparts = []
    if kind == "saved" and row.get("location"):
        subparts.append(str(row["location"]))
    if kind == "applications" and row.get("applied_at"):
        subparts.append("Ứng tuyển: " + str(row["applied_at"]))
    if kind == "invites" and row.get("sent_at"):
        subparts.append("Nhận lời mời: " + str(row["sent_at"]))
    if kind == "saved" and row.get("applied"):
        subparts.append("Đã ứng tuyển")
    if subparts:
        meta = QLabel("  •  ".join(subparts))
        meta.setObjectName("CandidateCardMeta")
        meta.setWordWrap(True)
        main.addWidget(meta)
    outer.addLayout(main, 1)

    state = QLabel(status_label(row.get("status")))
    state.setObjectName("CandidateCardStatus")
    state.setWordWrap(True)
    state.setAlignment(Qt.AlignmentFlag.AlignCenter)
    state.setMaximumWidth(138)
    outer.addWidget(state, 0, Qt.AlignmentFlag.AlignTop)
    return root
