from dataclasses import dataclass

@dataclass(frozen=True)
class Verification:
    ok: bool
    confidence: str
    reason: str


def verify_search_result(answer: str, sources: list[dict]) -> Verification:
    if not sources:
        return Verification(False, "منخفضة 🔴", "لا توجد مصادر يمكن التحقق منها.")
    valid_urls = sum(1 for source in sources if source.get("url"))
    if valid_urls >= 2:
        return Verification(True, "متوسطة 🟡", "توجد عدة مصادر قابلة للتتبع؛ قد تحتاج الادعاءات المهمة إلى مقارنة إضافية.")
    return Verification(True, "منخفضة 🟠", "يوجد مصدر قابل للتتبع واحد فقط.")
