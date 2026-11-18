-- İlan olgu tablosu: dashboard ve eşleştirme bu tablodan okur.
select
    job_id,
    md5(lower(company))     as company_id,
    title,
    company                 as company_name,
    city,
    district,
    is_remote,
    job_type,
    job_type_raw,
    location_raw,
    source,
    source_job_id,
    url,
    description,
    posted_at,
    posted_date,
    scraped_at
from {{ ref('stg_jobs') }}
