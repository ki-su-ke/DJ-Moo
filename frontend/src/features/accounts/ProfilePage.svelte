<script lang="ts">
  import { Building2, KeyRound, Mail, RefreshCw, ShieldCheck } from '@lucide/svelte'
  import type { UserProfile } from './api'

  let { profile, loadingProfile, error, onrefresh }: { profile: UserProfile | null; loadingProfile: boolean; error: string; onrefresh: () => Promise<void> } = $props()
</script>

<section class="content-wrap">
  <div class="page-heading">
    <div><div class="section-kicker">PERSONAL / OVERVIEW</div><h1>プロフィール</h1><p>アカウントと所属組織の情報。</p></div>
    <div class="record-count"><span class="status-dot"></span>アカウント情報</div>
  </div>
  {#if error}<div class="callout error-callout" role="alert">{error}<button class="icon-button" onclick={onrefresh} aria-label="再読み込み" title="再読み込み"><RefreshCw size={17} /></button></div>{/if}
  {#if loadingProfile}
    <div class="loading-line">プロフィールを読み込んでいます…</div>
  {:else if profile}
    <section class="profile-panel">
      <div class="panel-title"><span class="panel-icon"><Mail size={18} /></span><div><h2>基本情報</h2><p>アカウントに登録されている情報</p></div><span class="active-label"><span class="status-dot"></span>{profile.is_active ? '有効' : '無効'}</span></div>
      <dl class="detail-list"><div><dt>メールアドレス</dt><dd>{profile.email}</dd></div><div><dt>アカウント ID</dt><dd class="mono">{profile.id}</dd></div><div><dt>登録日</dt><dd>{new Date(profile.created_at).toLocaleDateString('ja-JP')}</dd></div></dl>
    </section>
    <div class="section-title-row"><div><div class="section-kicker">ORGANIZATION ACCESS</div><h2>所属組織</h2></div><span class="count-pill">{profile.memberships.length} 件</span></div>
    {#if profile.memberships.length}
      <div class="organization-list">
        {#each profile.memberships as membership (membership.id)}
          <article class="organization-row">
            <span class="org-icon"><Building2 size={21} /></span>
            <div class="org-main"><strong>{membership.organization.name}</strong><span>{membership.organization.slug}</span></div>
            <div class="role-group">{#each membership.roles as role (role.id)}<span class="role-chip">{role.name}</span>{/each}{#if membership.is_org_admin}<span class="admin-chip"><ShieldCheck size={13} />管理者</span>{/if}</div>
            <span class="scope-label">{membership.scope_type === 'all' ? '組織全体' : '担当分'}</span>
          </article>
        {/each}
      </div>
    {:else}
      <div class="empty-state"><Building2 size={24} /><p>現在、所属している組織はありません。</p></div>
    {/if}
    <div class="account-shortcuts"><a href="/account/change-password"><span><KeyRound size={18} /></span><div><strong>パスワード変更</strong><small>メールで届くリンクから変更します</small></div><span class="shortcut-arrow">↗</span></a><a href="/account/change-email"><span><Mail size={18} /></span><div><strong>メールアドレス変更</strong><small>新しいアドレスに確認メールを送信します</small></div><span class="shortcut-arrow">↗</span></a></div>
  {/if}
</section>