create extension if not exists pgmq;

select pgmq.create('example_jobs');

create table public.example_jobs (
  id uuid primary key,
  idempotency_key text not null unique,
  payload_hash char(64) not null,
  label text not null check (char_length(label) between 1 and 100),
  status text not null check (status in ('queued', 'running', 'succeeded', 'failed')),
  attempt_count integer not null default 0 check (attempt_count >= 0),
  result text,
  error_category text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz
);

create index example_jobs_status_created_at_idx
  on public.example_jobs (status, created_at);

alter table public.example_jobs enable row level security;

insert into storage.buckets (id, name, public, file_size_limit)
values ('vendor-documents', 'vendor-documents', false, 10485760)
on conflict (id) do update
set public = excluded.public,
    file_size_limit = excluded.file_size_limit;
