{#
  Türkçe karakterleri sadeleştirip küçük harfe çevirir: 'İstanbul / Şişli' → 'istanbul / sisli'.
  translate() lower()'dan ÖNCE çalışır; böylece 'I' ve 'İ' ikisi de 'i' olur.
  Python tarafındaki scraper.text.fold_turkish ile aynı mantık.
#}
{% macro fold_tr(expr) -%}
    lower(translate({{ expr }}, 'İIıŞşĞğÜüÖöÇçÂâÎîÛû', 'iiissgguuooccaaiiuu'))
{%- endmacro %}
