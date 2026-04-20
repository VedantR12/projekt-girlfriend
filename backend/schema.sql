-- -------------------------------------------------
-- Supabase SQL schema for Projekt Girlfriend backend
-- -------------------------------------------------

-- Users table – we will use Supabase Auth's built‑in auth.users table.
-- For reference we store a profile row with extra fields.
create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    created_at timestamp with time zone default now()
);

-- Personas – each persona belongs to a user.
create table if not exists public.personas (
    id uuid default uuid_generate_v4() primary key,
    user_id uuid references auth.users(id) on delete cascade,
    persona_name text not null,
    persona_json jsonb not null,
    created_at timestamp with time zone default now()
);

-- Long‑term memories extracted from the uploaded chat.
create table if not exists public.memories (
    id uuid default uuid_generate_v4() primary key,
    user_id uuid references auth.users(id) on delete cascade,
    persona_id uuid references public.personas(id) on delete cascade,
    text text not null,
    type text not null,
    importance double precision not null check (importance >= 0 and importance <= 1),
    created_at timestamp with time zone default now()
);

-- Live memories – captured after each conversation turn.
create table if not exists public.live_memories (
    id uuid default uuid_generate_v4() primary key,
    user_id uuid references auth.users(id) on delete cascade,
    persona_id uuid references public.personas(id) on delete cascade,
    text text not null,
    type text not null,
    importance double precision not null check (importance >= 0 and importance <= 1),
    created_at timestamp with time zone default now()
);

-- Conversation history – stores every message exchanged.
create table if not exists public.conversations (
    id uuid default uuid_generate_v4() primary key,
    user_id uuid references auth.users(id) on delete cascade,
    persona_id uuid references public.personas(id) on delete cascade,
    message text not null,
    sender text check (sender in ('user','persona')) not null,
    created_at timestamp with time zone default now()
);

-- API keys – encrypted Groq key per user (BYOK).
create table if not exists public.api_keys (
    id uuid default uuid_generate_v4() primary key,
    user_id uuid references auth.users(id) on delete cascade,
    encrypted_key bytea not null,
    created_at timestamp with time zone default now()
);

-- Indexes for fast lookup
create index if not exists idx_memories_user_persona on public.memories(user_id, persona_id);
create index if not exists idx_live_memories_user_persona on public.live_memories(user_id, persona_id);
create index if not exists idx_conversations_user_persona on public.conversations(user_id, persona_id, created_at desc);

-- Enable row level security (RLS) – only the owner can read/write.
alter table public.personas enable row level security;
alter table public.memories enable row level security;
alter table public.live_memories enable row level security;
alter table public.conversations enable row level security;
alter table public.api_keys enable row level security;

create policy "owner can access" on public.personas for all using (auth.uid() = user_id);
create policy "owner can access" on public.memories for all using (auth.uid() = user_id);
create policy "owner can access" on public.live_memories for all using (auth.uid() = user_id);
create policy "owner can access" on public.conversations for all using (auth.uid() = user_id);
create policy "owner can access" on public.api_keys for all using (auth.uid() = user_id);
