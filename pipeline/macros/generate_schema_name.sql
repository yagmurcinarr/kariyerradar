{#
  dbt varsayılan olarak şemayı "<hedef>_<özel>" (ör. public_staging) diye adlandırır.
  Bu makro özel şema adını olduğu gibi kullanır: staging, marts, seeds.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
