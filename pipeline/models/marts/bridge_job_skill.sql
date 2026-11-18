{#
  İlan–beceri köprü tablosu: ilan başlığı + açıklamasında geçen becerileri bulur.
  Eşleme regex ile ve kelime sınırıyla yapılır:
    - "sql" → "MySQL" içinde eşleşmez, "java" → "JavaScript" içinde eşleşmez
    - case_sensitive=true becerilerde (Excel, React, Unity...) büyük/küçük harf korunur;
      böylece "excel at", "react quickly" gibi İngilizce fiiller beceri sayılmaz.
#}

with aliases as (

    -- Her becerinin aranacak yazılışları (aliases sütunu '|' ile ayrılmış).
    -- Beceri adı otomatik eklenmez: "Go" ve "R" gibi adlar İngilizce metinde yanlış eşleşir.
    select distinct
        s.skill_id,
        s.case_sensitive,
        trim(alias) as alias
    from {{ ref('skills') }} as s
    cross join lateral unnest(string_to_array(s.aliases, '|')) as alias
    where trim(alias) <> ''

),

patterns as (

    select
        skill_id,
        case_sensitive,
        -- Önce regex özel karakterlerini kaçır (c++ → c\+\+), sonra kelime sınırı ekle.
        -- Sınırda harf/rakam ve + # olmamalı: "c#" → "c#m" eşleşmez, "c++" → "c+++" eşleşmez.
        '(^|[^A-Za-z0-9+#])'
            || regexp_replace(
                case when case_sensitive then alias else {{ fold_tr('alias') }} end,
                '([.+*?^$(){}|\[\]\\#/-])', '\\\1', 'g'
            )
            || '($|[^A-Za-z0-9+#])' as pattern
    from aliases

),

jobs as (

    select
        job_id,
        title || E'\n' || coalesce(description, '')                    as text_raw,
        {{ fold_tr("title || E'\\n' || coalesce(description, '')") }}  as text_folded
    from {{ ref('stg_jobs') }}

),

matches as (

    select distinct
        j.job_id,
        p.skill_id
    from jobs as j
    inner join patterns as p
        on case
            when p.case_sensitive then j.text_raw ~ p.pattern
            else j.text_folded ~ p.pattern
        end

)

select
    job_id || '-' || skill_id   as job_skill_id,
    job_id,
    skill_id
from matches
