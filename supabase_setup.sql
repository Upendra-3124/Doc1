-- ============================================================
--  DocShare – Run this entire file in Supabase SQL Editor
-- ============================================================

create table if not exists public.files (
    id           uuid primary key default gen_random_uuid(),
    username     text not null,
    title        text not null,
    file_url     text not null,
    file_path    text,
    thumb_url    text,
    thumb_path   text,
    file_type    text not null,
    uploaded_at  timestamptz default now()
);

create index if not exists files_username_idx on public.files (username);

alter table public.files enable row level security;

create policy "public_read"   on public.files for select using (true);
create policy "public_insert" on public.files for insert with check (true);
create policy "public_update" on public.files for update using (true);
create policy "public_delete" on public.files for delete using (true);

-- Storage buckets
insert into storage.buckets (id, name, public)
  values ('docshare-files', 'docshare-files', true)
  on conflict (id) do nothing;

insert into storage.buckets (id, name, public)
  values ('docshare-thumbs', 'docshare-thumbs', true)
  on conflict (id) do nothing;

create policy "public_upload_files"  on storage.objects for insert with check (bucket_id = 'docshare-files');
create policy "public_read_files"    on storage.objects for select using  (bucket_id = 'docshare-files');
create policy "public_delete_files"  on storage.objects for delete using  (bucket_id = 'docshare-files');
create policy "public_upload_thumbs" on storage.objects for insert with check (bucket_id = 'docshare-thumbs');
create policy "public_read_thumbs"   on storage.objects for select using  (bucket_id = 'docshare-thumbs');
create policy "public_delete_thumbs" on storage.objects for delete using  (bucket_id = 'docshare-thumbs');
