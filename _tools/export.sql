-- изменено 2026-09-30 19:00
-- Выгрузка живых вакансий (без контактов!) для генератора SEO-страниц. Только чтение.
-- Копии одного объявления схлопнуты по ключу «телефон+должность+город» с самой свежей датой
-- (тот же ключ, что api/vacancies.py::_ckey_sql — держать в паре).
-- Запуск (с рабочего мака): ssh imac '/Applications/Postgres.app/Contents/Versions/latest/bin/psql "$DATABASE_URL" -qAtX -f -' < _tools/export.sql > _tools/data.json
SET default_transaction_read_only = on;
SELECT json_agg(t) FROM (
  SELECT DISTINCT ON (ckey) id, position, company, city, salary_text, salary_amount, salary_currency,
         schedule, no_experience, employment_type, duties, last_seen_at
  FROM (
    SELECT v.*, CASE WHEN coalesce(nullif(right(regexp_replace(coalesce(v.phone,''), '\D', '', 'g'), 9), ''), lower(coalesce(v.contact_username,''))) <> '' AND coalesce(v.position,'') <> '' THEN coalesce(nullif(right(regexp_replace(coalesce(v.phone,''), '\D', '', 'g'), 9), ''), lower(coalesce(v.contact_username,''))) || '|' || lower(btrim(v.position)) || '|' || lower(btrim(coalesce(v.city,''))) ELSE v.id END AS ckey
    FROM vacancies v
    WHERE v.is_vacancy AND NOT v.is_expired AND NOT v.suspicious AND v.status <> 'rejected'
      AND v.job_type = 'рядом' AND coalesce(v.country, 'Беларусь') = 'Беларусь'
      AND (coalesce(v.phone, '') <> '' OR coalesce(v.contact_username, '') <> '' OR coalesce(v.email, '') <> '')
      AND coalesce(v.position, '') <> '' AND coalesce(v.city, '') <> ''
  ) c
  ORDER BY ckey, last_seen_at DESC
) t;
