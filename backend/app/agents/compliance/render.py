"""
Human-readable rendering of a ClearanceReport.

The Pydantic object is the contract; this is what a creator actually reads, and
what you put on screen in a demo. Green passes quietly — the creator should not
scroll a wall of things that were fine.
"""

from typing import Iterable, List, Optional

from app.shared.models.compliance import (
    ClearanceReport,
    ClearanceStatus,
    ComplianceIssue,
    ReportStatus,
)

LIGHT = {
    ClearanceStatus.RED: "🔴 RED",
    ClearanceStatus.YELLOW: "🟡 YELLOW",
    ClearanceStatus.GREEN: "🟢 GREEN",
    ClearanceStatus.UNVERIFIED: "⚪ UNVERIFIED",
}

ORDER = [
    ClearanceStatus.RED,
    ClearanceStatus.YELLOW,
    ClearanceStatus.UNVERIFIED,
    ClearanceStatus.GREEN,
]


def _wrap(text: str, indent: str = "   ", width: int = 72) -> str:
    words = (text or "").split()
    lines: List[str] = []
    current = ""

    for word in words:
        if len(current) + len(word) + 1 > width:
            lines.append(indent + current)
            current = word
        else:
            current = f"{current} {word}".strip()

    if current:
        lines.append(indent + current)

    return "\n".join(lines)


def _render_issue(issue: ComplianceIssue) -> str:
    heading = issue.label or issue.kind.value.replace("_", " ")

    out = [f"{LIGHT[issue.severity]} — {heading}"]
    out.append(_wrap(issue.description))

    for ref in issue.evidence:
        out.append(_wrap(f"{ref.claim}  → {ref.url}"))

    if issue.recommended_action:
        out.append(_wrap(f"ACTION: {issue.recommended_action}"))

    for sub in issue.substitutes:
        out.append(_wrap(f"SUBSTITUTE: {sub}"))

    if issue.severity in (ClearanceStatus.RED, ClearanceStatus.YELLOW) and not issue.evidence:
        out.append(_wrap("No source attached."))

    return "\n".join(out)


def render_report(
    report: ClearanceReport,
    project_name: Optional[str] = None,
    carried_forward: Optional[Iterable[str]] = None,
) -> str:
    lines: List[str] = [
        f"CLEARANCE REPORT — pass {report.pass_number} of 6 "
        f"(after {report.stage})",
    ]

    if project_name:
        lines.append(f'Project: "{project_name}"')

    lines.append("")

    if report.structural_errors:
        lines.append("STRUCTURAL ERRORS")
        for err in report.structural_errors:
            lines.append(f"   • {err}")
        lines.append("")

    shown = 0
    for status in ORDER:
        for issue in report.issues:
            if issue.severity is not status:
                continue
            lines.append(_render_issue(issue))
            lines.append("")
            shown += 1

    if not shown and not report.structural_errors:
        lines.append("No rights-bearing items found at this stage.")
        lines.append("")

    if carried_forward:
        lines.append("CARRIED FORWARD")
        for item in carried_forward:
            lines.append(f"   {item}")
        lines.append("")

    if report.degraded_reasons:
        lines.append("VERIFICATION GAPS")
        for reason in report.degraded_reasons:
            lines.append(_wrap(f"• {reason}"))
        lines.append("")

    reds = len(report.reds)
    yellows = len(report.yellows)

    if report.status is ReportStatus.BLOCKED:
        tail = f"BLOCKED on {reds} red" + ("s" if reds != 1 else "")
        if report.structural_errors:
            tail = "BLOCKED on structural errors"
    elif report.status is ReportStatus.DEGRADED:
        tail = "DEGRADED — some items could not be verified. Do not treat as passed."
    elif report.status is ReportStatus.PASSED_WITH_CONDITIONS:
        tail = f"PASSED with {yellows} open task" + ("s" if yellows != 1 else "")
    else:
        tail = "PASSED"

    lines.append(f"PIPELINE STATUS: {tail}")

    return "\n".join(lines)