-- Run once in the Supabase SQL editor; safe to re-run.
-- This schema is for a server-mediated private classroom demo. A backend secret
-- key is stored only on the Streamlit server. The app's demo gate and membership
-- checks protect access; the account picker is not university authentication.
begin;

create table if not exists public.eir_ventures (
    id text primary key check (id ~ '^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$'),
    payload jsonb not null check (jsonb_typeof(payload) = 'object' and payload ? 'id' and payload->>'id' = id),
    revision bigint not null check (revision > 0),
    updated_at timestamptz not null default now()
);

create table if not exists public.eir_venture_versions (
    venture_id text not null references public.eir_ventures(id),
    revision bigint not null check (revision > 0),
    payload jsonb not null,
    saved_at timestamptz not null default now(),
    primary key (venture_id, revision)
);

alter table public.eir_ventures enable row level security;
alter table public.eir_venture_versions enable row level security;
revoke all on table public.eir_ventures, public.eir_venture_versions from public, anon, authenticated;
revoke all on table public.eir_ventures, public.eir_venture_versions from service_role;
grant select on table public.eir_ventures, public.eir_venture_versions to service_role;

create or replace function public.eir_save_venture(
    p_id text, p_payload jsonb, p_expected_revision bigint
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    next_revision bigint;
begin
    if p_id is null or p_id !~ '^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$'
       or p_payload is null or jsonb_typeof(p_payload) <> 'object'
       or p_payload->>'id' is distinct from p_id
       or p_expected_revision is null or p_expected_revision < 0 then
        raise sqlstate '22023' using message = 'Invalid project snapshot';
    end if;

    if p_expected_revision = 0 then
        insert into public.eir_ventures(id, payload, revision)
        values (p_id, p_payload, 1)
        on conflict (id) do nothing
        returning revision into next_revision;
    else
        update public.eir_ventures
        set payload = p_payload, revision = revision + 1, updated_at = now()
        where id = p_id and revision = p_expected_revision
        returning revision into next_revision;
    end if;

    if next_revision is null then
        raise sqlstate 'PT409' using message = 'Project changed; reload before saving';
    end if;

    insert into public.eir_venture_versions(venture_id, revision, payload)
    values (p_id, next_revision, p_payload);
    return jsonb_build_object('revision', next_revision);
end;
$$;

revoke all on function public.eir_save_venture(text, jsonb, bigint) from public, anon, authenticated;
grant execute on function public.eir_save_venture(text, jsonb, bigint) to service_role;

-- Default bucket is private. Object upload/download/removal go through the
-- Storage API; do not write directly to storage.objects.
insert into storage.buckets(id, name, public, file_size_limit)
values ('eir-files', 'eir-files', false, 20971520)
on conflict (id) do update set public = false;

notify pgrst, 'reload schema';
commit;
