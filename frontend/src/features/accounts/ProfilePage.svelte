<script lang="ts">
  import { Building2, KeyRound, Mail, RefreshCw, ShieldCheck, Trash2 } from '@lucide/svelte'
  import { getOrganizationMembers, removeOrganizationMember, type OrganizationMember, type UserProfile } from './api'

  let { profile, loadingProfile, error, onrefresh, ondeleteaccount }: { profile: UserProfile | null; loadingProfile: boolean; error: string; onrefresh: () => Promise<void>; ondeleteaccount: () => Promise<void> } = $props()
  let expandedOrganizationId = $state('')
  let organizationMembers = $state<OrganizationMember[]>([])
  let loadingMembers = $state(false)
  let membersError = $state('')
  let membersSuccess = $state('')
  let pendingRemovalId = $state('')
  let removingMembershipId = $state('')
  let showAccountDeletion = $state(false)
  let accountConfirmation = $state('')
  let deletingAccount = $state(false)
  let accountDeleteError = $state('')

  /** Admin が対象組織のメンバー一覧を開閉する。 */
  async function toggleMembers(membership: UserProfile['memberships'][number]) {
    membersError = ''
    membersSuccess = ''
    pendingRemovalId = ''
    if (expandedOrganizationId === membership.id) {
      expandedOrganizationId = ''
      return
    }

    expandedOrganizationId = membership.id
    organizationMembers = []
    loadingMembers = true
    try {
      const response = await getOrganizationMembers(membership.organization.slug)
      if (expandedOrganizationId === membership.id) organizationMembers = response.members
    } catch (requestError) {
      if (expandedOrganizationId === membership.id) {
        membersError = requestError instanceof Error ? requestError.message : 'メンバー一覧を取得できませんでした。'
      }
    } finally {
      if (expandedOrganizationId === membership.id) loadingMembers = false
    }
  }

  /** 選択したメンバーを現在の組織からだけ外す。 */
  async function removeMember(membership: UserProfile['memberships'][number], member: OrganizationMember) {
    removingMembershipId = member.id
    membersError = ''
    membersSuccess = ''
    try {
      await removeOrganizationMember(membership.organization.slug, member.id)
      organizationMembers = organizationMembers.filter((item) => item.id !== member.id)
      pendingRemovalId = ''
      membersSuccess = `${member.email} をこの組織から外しました。`
    } catch (requestError) {
      membersError = requestError instanceof Error ? requestError.message : 'メンバーを削除できませんでした。'
    } finally {
      removingMembershipId = ''
    }
  }

  /** 確認語の一致を確認してから退会処理を呼び出す。 */
  async function submitAccountDeletion(event: SubmitEvent) {
    event.preventDefault()
    if (accountConfirmation !== 'DELETE') return

    deletingAccount = true
    accountDeleteError = ''
    try {
      await ondeleteaccount()
    } catch (requestError) {
      accountDeleteError = requestError instanceof Error ? requestError.message : '退会処理に失敗しました。'
      deletingAccount = false
    }
  }
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
            {#if membership.is_org_admin}
              <div class="member-management">
                <button class="member-toggle" onclick={() => void toggleMembers(membership)} aria-expanded={expandedOrganizationId === membership.id}>
                  <Building2 size={15} />{expandedOrganizationId === membership.id ? 'メンバー管理を閉じる' : 'メンバーを管理'}
                </button>
                {#if expandedOrganizationId === membership.id}
                  <div class="member-list-panel">
                    <h3>{membership.organization.name} のメンバー</h3>
                    {#if loadingMembers}<p class="member-status">メンバーを読み込んでいます…</p>{/if}
                    {#if membersError}<p class="form-error" role="alert">{membersError}</p>{/if}
                    {#if membersSuccess}<p class="form-success" role="status">{membersSuccess}</p>{/if}
                    {#each organizationMembers as member (member.id)}
                      <div class="member-row">
                        <div class="member-identity"><strong>{member.email}</strong>{#if member.is_org_admin}<span class="admin-chip"><ShieldCheck size={12} />管理者</span>{/if}</div>
                        {#if member.user_id === profile.id}
                          <span class="member-self">自分</span>
                        {:else if pendingRemovalId === member.id}
                          <div class="member-confirm">
                            <span>この組織から外します。アカウント自体は削除されません。</span>
                            <button class="secondary-button" onclick={() => pendingRemovalId = ''}>キャンセル</button>
                            <button class="danger-action" disabled={removingMembershipId === member.id} onclick={() => void removeMember(membership, member)}><Trash2 size={14} />外す</button>
                          </div>
                        {:else}
                          <button class="member-remove" aria-label="{member.email} を組織から外す" title="組織から外す" onclick={() => pendingRemovalId = member.id}><Trash2 size={16} /></button>
                        {/if}
                      </div>
                    {/each}
                  </div>
                {/if}
              </div>
            {/if}
          </article>
        {/each}
      </div>
    {:else}
      <div class="empty-state"><Building2 size={24} /><p>現在、所属している組織はありません。</p></div>
    {/if}
    <div class="account-shortcuts"><a href="/account/change-password"><span><KeyRound size={18} /></span><div><strong>パスワード変更</strong><small>メールで届くリンクから変更します</small></div><span class="shortcut-arrow">↗</span></a><a href="/account/change-email"><span><Mail size={18} /></span><div><strong>メールアドレス変更</strong><small>新しいアドレスに確認メールを送信します</small></div><span class="shortcut-arrow">↗</span></a></div>
    <section class="danger-zone" aria-labelledby="account-deletion-title">
      <div class="danger-copy"><div class="section-kicker">ACCOUNT</div><h2 id="account-deletion-title">アカウント退会</h2><p>アカウント情報を匿名化して無効化し、すべての組織から退会します。この操作は取り消せません。</p></div>
      {#if !showAccountDeletion}
        <button class="danger-button" onclick={() => showAccountDeletion = true}><Trash2 size={16} />退会手続きへ</button>
      {:else}
        <form class="danger-confirmation" onsubmit={submitAccountDeletion}>
          <label for="account-delete-confirmation">確認のため DELETE と入力してください</label>
          <input id="account-delete-confirmation" bind:value={accountConfirmation} autocomplete="off" />
          {#if accountDeleteError}<p class="form-error" role="alert">{accountDeleteError}</p>{/if}
          <div class="danger-actions">
            <button type="button" class="secondary-button" onclick={() => { showAccountDeletion = false; accountConfirmation = ''; accountDeleteError = '' }}>キャンセル</button>
            <button type="submit" class="danger-button" disabled={accountConfirmation !== 'DELETE' || deletingAccount}><Trash2 size={16} />{deletingAccount ? '処理中…' : 'アカウントを退会'}</button>
          </div>
        </form>
      {/if}
    </section>
  {/if}
</section>