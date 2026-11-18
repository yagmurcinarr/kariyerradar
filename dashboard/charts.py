"""Altair grafik yardımcıları. Tüm grafikler tek seri olduğu için tek renk kullanılır;
ince işaretler, 4px yuvarlatılmış bar uçları ve üzerine gelince açılan ipucu (tooltip).
"""

import altair as alt
import pandas as pd

SERIES_COLOR = "#2a78d6"  # tek seri rengi (açık ve koyu temada okunur)
BAR_ROW_HEIGHT = 30  # yatay barlarda satır başına piksel


def horizontal_bar(
    data: pd.DataFrame,
    category: str,
    value: str,
    value_title: str,
    tooltip: list[alt.Tooltip],
) -> alt.Chart:
    """Çoktan aza sıralı yatay bar grafiği (sıralama/kıyas için)."""
    return (
        alt.Chart(data)
        .mark_bar(color=SERIES_COLOR, cornerRadiusEnd=4, height={"band": 0.7})
        .encode(
            # labelOverlap=False: Altair sıkışınca etiketleri gizlemesin, her çubuk adlı kalsın
            y=alt.Y(
                f"{category}:N",
                sort="-x",
                title=None,
                axis=alt.Axis(labelLimit=220, labelOverlap=False),
            ),
            x=alt.X(
                f"{value}:Q",
                title=value_title,
                axis=alt.Axis(tickMinStep=1, format="d", gridOpacity=0.4),
            ),
            tooltip=tooltip,
        )
        .properties(height=max(120, BAR_ROW_HEIGHT * len(data)))
    )


def weekly_line(data: pd.DataFrame) -> alt.Chart:
    """Haftalık ilan sayısı çizgisi; noktalar ipucu için büyük vuruş alanı sağlar."""
    base = alt.Chart(data).encode(
        x=alt.X("week_start:T", title=None, axis=alt.Axis(format="%d.%m", labelAngle=0)),
        y=alt.Y(
            "job_count:Q",
            title="İlan sayısı",
            axis=alt.Axis(tickMinStep=1, format="d", gridOpacity=0.4),
        ),
        tooltip=[
            alt.Tooltip("week_start:T", title="Hafta başı", format="%d %B %Y"),
            alt.Tooltip("job_count:Q", title="İlan"),
        ],
    )
    line = base.mark_line(color=SERIES_COLOR, strokeWidth=2)
    points = base.mark_point(color=SERIES_COLOR, filled=True, size=70)
    return (line + points).properties(height=280)
