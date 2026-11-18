"""Saf (ağ kullanmayan) metin yardımcıları: HTML → düz metin, kişisel veri temizliği,
Türkiye lokasyon kontrolü. Hepsi kolayca birim test edilebilir.
"""

import re
import unicodedata

from bs4 import BeautifulSoup

REDACTED = "[kaldırıldı]"

# ad.soyad@firma.com gibi e-posta adresleri
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")

# Türkiye telefon biçimleri: +90 532 123 45 67, 0(212) 123 45 67, 05321234567 ...
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?90[\s.-]?)?0?\(?0?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}(?!\d)"
)

# 81 il (ASCII'ye katlanmış) + ülke adları.
# Kelime sınırıyla aranır ki "Vancouver" içindeki "van" eşleşmesin.
_TURKEY_TERMS = """
turkey turkiye türkiye adana adiyaman afyonkarahisar agri amasya ankara antalya artvin aydin
balikesir bilecik bingol bitlis bolu burdur bursa canakkale cankiri corum denizli diyarbakir
edirne elazig erzincan erzurum eskisehir gaziantep giresun gumushane hakkari hatay isparta mersin
istanbul izmir kars kastamonu kayseri kirklareli kirsehir kocaeli konya kutahya malatya manisa
kahramanmaras mardin mugla mus nevsehir nigde ordu rize sakarya samsun siirt sinop sivas tekirdag
tokat trabzon tunceli sanliurfa usak van yozgat zonguldak aksaray bayburt karaman kirikkale batman
sirnak bartin ardahan igdir yalova karabuk kilis osmaniye duzce
""".split()
_TURKEY_RE = re.compile(r"\b(?:" + "|".join(sorted(set(_TURKEY_TERMS))) + r")\b")


def fold_turkish(text: str) -> str:
    """Küçük harfe çevirip Türkçe karakterleri sadeleştirir: 'İstanbul/Şişli' → 'istanbul/sisli'."""
    text = text.replace("ı", "i").replace("İ", "i").casefold()
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def is_turkey_location(text: str | None) -> bool:
    """Lokasyon metni Türkiye'de bir yeri gösteriyorsa True."""
    return bool(text) and _TURKEY_RE.search(fold_turkish(text)) is not None


# Satır sonu sadece bu "blok" etiketlerde konur; <strong>, <span>, <a> gibi satır içi
# etiketler cümleyi bölmesin.
_BLOCK_TAGS = ["p", "div", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section"]


def html_to_text(html: str | None) -> str:
    """HTML'i okunabilir düz metne çevirir; liste maddelerini '- ' ile başlatır."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for tag in soup.find_all(_BLOCK_TAGS):
        tag.insert_before("\n\n")
        tag.insert_after("\n\n")
    for li in soup.find_all("li"):
        li.insert_before("\n- ")
        li.insert_after("\n")
    text = soup.get_text()
    lines = (re.sub(r"[ \t ]+", " ", line).strip() for line in text.splitlines())
    text = "\n".join(lines)
    text = re.sub(r"^-\s*\n+", "- ", text, flags=re.M)  # "- \n\nmadde" → "- madde"
    # Ardışık liste maddeleri arasında boş satır olmasın
    text = re.sub(r"^(- .*)\n{2,}(?=- )", r"\1\n", text, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def scrub_pii(text: str) -> str:
    """İlan metnindeki e-posta ve telefon numaralarını siler (kişisel veri toplamıyoruz)."""
    text = _EMAIL_RE.sub(REDACTED, text)
    return _PHONE_RE.sub(REDACTED, text)


def clean_description(html: str | None) -> str | None:
    """HTML açıklamayı düz metne çevirip kişisel verileri temizler; boşsa None döner."""
    text = scrub_pii(html_to_text(html))
    return text or None
