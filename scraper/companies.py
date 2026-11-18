"""Hangi şirketin ilanlarının hangi ATS'den (aday takip sistemi) okunacağı.

Bu ATS'lerin ilan API'leri herkese açıktır ve şirketlerin ilanlarını dış sitelerde
yayınlamaları için tasarlanmıştır. Yeni şirket eklemek için listeye bir satır eklemek yeterli.
Slug, şirketin kariyer sayfası adresindeki addır: jobs.lever.co/<slug>.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CompanyBoard:
    """Bir şirketin belirli bir ATS'deki ilan panosu."""

    name: str  # Görünen şirket adı
    ats: str  # "lever" | "greenhouse" | "workable"
    slug: str  # ATS'deki pano adı


BOARDS: tuple[CompanyBoard, ...] = (
    # --- Lever ---
    CompanyBoard("Trendyol", "lever", "trendyol"),
    CompanyBoard("Insider One", "lever", "insiderone"),
    CompanyBoard("Dream Games", "lever", "dreamgames"),
    CompanyBoard("Cypher Games", "lever", "cypher-games"),
    CompanyBoard("Commencis", "lever", "commencis"),
    CompanyBoard("Spyke Games", "lever", "spyke-games"),
    CompanyBoard("Picus Security", "lever", "picus"),
    CompanyBoard("iyzico", "lever", "iyzico"),
    # --- Greenhouse ---
    CompanyBoard("Good Job Games", "greenhouse", "goodjobgames"),
    CompanyBoard("Medsien", "greenhouse", "medsien"),
    CompanyBoard("OKX", "greenhouse", "okx"),
    CompanyBoard("OLIVER Agency", "greenhouse", "oliver"),
    # --- Workable ---
    CompanyBoard("Vertigo Games", "workable", "vertigogames"),
    CompanyBoard("Teltonika", "workable", "teltonika"),
    CompanyBoard("Ace Games", "workable", "ace-games"),
)


def boards_for(ats: str) -> list[CompanyBoard]:
    """Verilen ATS'ye ait panoları döndürür."""
    return [b for b in BOARDS if b.ats == ats]
