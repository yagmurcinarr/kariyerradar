-- Beceri boyutu: seeds/skills.csv sözlüğünden.
select
    skill_id,
    skill_name,
    category
from {{ ref('skills') }}
