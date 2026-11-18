-- Firma boyutu: her firma bir satır. company_id, firma adından türetilen kararlı bir anahtar.
select
    md5(lower(company))     as company_id,
    max(company)            as company_name,
    count(*)                as job_count,
    min(scraped_at)         as first_seen_at,
    max(scraped_at)         as last_seen_at
from {{ ref('stg_jobs') }}
group by md5(lower(company))
