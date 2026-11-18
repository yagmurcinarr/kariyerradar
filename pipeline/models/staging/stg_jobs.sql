{#
  stg_jobs: ham ilanları temizler ve standartlaştırır.
    - Metinlerdeki fazla boşlukları temizler
    - location_raw'dan şehir ve ilçe çıkarır ("Istanbul / Maslak" → İstanbul, Maslak)
    - İş türünü başlık + job_type_raw'dan sınıflandırır: staj | yeni_mezun | junior | diger
#}

with source as (

    select * from {{ source('raw', 'job_postings') }}

),

cleaned as (

    select
        id                                                  as job_id,
        source,
        source_job_id,
        trim(url)                                           as url,
        regexp_replace(trim(title), '\s+', ' ', 'g')        as title,
        regexp_replace(trim(company), '\s+', ' ', 'g')      as company,
        nullif(trim(location_raw), '')                      as location_raw,
        nullif(trim(job_type_raw), '')                      as job_type_raw,
        nullif(trim(description), '')                       as description,
        posted_at,
        scraped_at,
        -- Eşleştirmeler için sadeleştirilmiş (küçük harf, Türkçe karaktersiz) metinler
        {{ fold_tr("coalesce(location_raw, '')") }}         as location_folded,
        {{ fold_tr("title || ' ' || coalesce(job_type_raw, '')") }} as type_text
    from source

),

-- Lokasyon metninde geçen ilk ili bul (çok şehirli ilanlarda ilk şehir = ana şehir)
city_match as (

    select distinct on (c.job_id)
        c.job_id,
        ci.city_key,
        ci.city_name
    from cleaned as c
    inner join {{ ref('cities') }} as ci
        on c.location_folded ~ ('\m' || ci.city_key || '\M')   -- \m \M: kelime sınırı
    order by c.job_id, regexp_instr(c.location_folded, '\m' || ci.city_key || '\M')

),

-- İlçe: ilk lokasyon parçasında ("A / B, C | D" → "A / B, C") il ya da ülke olmayan ilk kelime grubu
district_match as (

    select distinct on (c.job_id)
        c.job_id,
        part.value as district
    from cleaned as c
    cross join lateral unnest(
        regexp_split_to_array(split_part(c.location_raw, '|', 1), '\s*[/,]\s*')
    ) with ordinality as part (value, position)
    where trim(part.value) <> ''
      and {{ fold_tr('part.value') }} not in ('turkey', 'turkiye', 'remote', 'uzaktan', 'hybrid')
      and not exists (
          select 1 from {{ ref('cities') }} as ci
          where {{ fold_tr('part.value') }} ~ ('\m' || ci.city_key || '\M')
      )
    order by c.job_id, part.position

),

final as (

    select
        c.job_id,
        c.source,
        c.source_job_id,
        c.url,
        c.title,
        c.company,
        c.location_raw,
        coalesce(
            cm.city_name,
            case when c.location_folded ~ '(remote|uzaktan)' then 'Uzaktan' end,
            'Belirtilmemiş'
        )                                                   as city,
        trim(dm.district)                                   as district,
        (c.location_folded ~ '(remote|uzaktan)'
            or c.type_text ~ '(remote|uzaktan)')            as is_remote,
        c.job_type_raw,
        case
            -- \m...\M kelime sınırı: "International" yanlışlıkla "intern" sayılmaz
            when c.type_text ~ '\m(intern|internship|stajyer|staj|stajer)\M'
                then 'staj'
            when c.type_text ~ '(new grad|\mgraduate\M|yeni mezun|entry[ -]level|\mtrainee\M)'
                then 'yeni_mezun'
            when c.type_text ~ '\m(junior|jr)\M'
                then 'junior'
            else 'diger'
        end                                                 as job_type,
        c.description,
        c.posted_at,
        coalesce(c.posted_at, c.scraped_at)::date           as posted_date,
        c.scraped_at
    from cleaned as c
    left join city_match as cm on cm.job_id = c.job_id
    left join district_match as dm on dm.job_id = c.job_id

)

select * from final
