<script lang="ts">
  import { onMount } from 'svelte'
  import { Building2, KeyRound, LogOut, Mail, ShieldCheck, UserRound } from '@lucide/svelte'
  import { authenticatedRequest, clearSession, login, logout, session } from './features/accounts/auth'
  import {
    deleteMyAccount,
    getProfile,
    requestEmailChange,
    requestPasswordChange,
    requestRegistration,
    type UserProfile,
  } from './features/accounts/api'
  import LoginPage from './features/accounts/LoginPage.svelte'
  import RegisterPage from './features/accounts/RegisterPage.svelte'
  import ProfilePage from './features/accounts/ProfilePage.svelte'
  import PasswordRequestPage from './features/accounts/PasswordRequestPage.svelte'
  import EmailRequestPage from './features/accounts/EmailRequestPage.svelte'

  let route = $state(window.location.pathname)
  let profile = $state<UserProfile | null>(null)
  let profileError = $state('')
  let loadingProfile = $state(false)
  let logoutError = $state('')
  const protectedRoutes = ['/profile', '/account/change-password', '/account/change-email']

  function navigate(path: string) {
    if (window.location.pathname !== path) window.history.pushState({}, '', path)
    setRoute(path)
  }

  function setRoute(path: string) {
    if (!['/login', '/register', ...protectedRoutes].includes(path)) path = '/login'
    if (protectedRoutes.includes(path) && !$session) path = '/login'
    if ((path === '/login' || path === '/register') && $session) path = '/profile'
    if (window.location.pathname !== path) window.history.replaceState({}, '', path)
    route = path
    if (path === '/profile') void loadProfile()
  }

  async function loadProfile() {
    loadingProfile = true
    profileError = ''
    try {
      profile = await getProfile()
    } catch (error) {
      profileError = error instanceof Error ? error.message : 'プロフィールを読み込めませんでした。'
    } finally {
      loadingProfile = false
    }
  }

  async function signIn(email: string, password: string) {
    await login(email, password)
    navigate('/profile')
  }

  async function signOut() {
    logoutError = ''
    try {
      await logout()
    } catch {
      logoutError = 'サーバーに接続できませんでした。端末内のログイン情報は削除しました。'
    }
    profile = null
    navigate('/login')
  }

  /** 退会成功後にセッションを破棄してログイン画面へ戻す。 */
  async function finishAccountDeletion() {
    await deleteMyAccount()
    clearSession()
    profile = null
    navigate('/login')
  }

  $effect(() => {
    if (!$session && protectedRoutes.includes(route)) navigate('/login')
  })

  onMount(() => {
    const onPopState = () => setRoute(window.location.pathname)
    window.addEventListener('popstate', onPopState)
    setRoute(window.location.pathname)
    return () => window.removeEventListener('popstate', onPopState)
  })
</script>

{#if $session}
  <div class="workspace-shell">
    <aside class="sidebar">
      <a class="brand" href="/profile" onclick={(event) => { event.preventDefault(); navigate('/profile') }}>
        <span class="brand-mark">M</span>
        <span><strong>DJ-MOO</strong><small>ACCOUNT CENTER</small></span>
      </a>
      <div class="side-label">PERSONAL</div>
      <nav aria-label="アカウントメニュー">
        <a class:active={route === '/profile'} href="/profile" onclick={(event) => { event.preventDefault(); navigate('/profile') }}>
          <UserRound size={18} />プロフィール
        </a>
        <a class:active={route === '/account/change-password'} href="/account/change-password" onclick={(event) => { event.preventDefault(); navigate('/account/change-password') }}>
          <KeyRound size={18} />パスワード
        </a>
        <a class:active={route === '/account/change-email'} href="/account/change-email" onclick={(event) => { event.preventDefault(); navigate('/account/change-email') }}>
          <Mail size={18} />メールアドレス
        </a>
      </nav>
      <div class="sidebar-bottom">
        <div class="sidebar-user"><span class="avatar">{profile?.email?.slice(0, 1).toUpperCase() ?? 'A'}</span><span class="user-copy"><strong>{profile?.email ?? 'アカウント'}</strong><small>個人アカウント</small></span></div>
        <button class="signout" onclick={signOut} aria-label="ログアウト" title="ログアウト"><LogOut size={17} /></button>
      </div>
    </aside>
    <main class="main-area">
      <header class="topbar"><span>MY ACCOUNT</span><button class="quiet-button" onclick={signOut}><LogOut size={16} />ログアウト</button></header>
      {#if logoutError}<p class="toast-error" role="alert">{logoutError}</p>{/if}
      {#if route === '/profile'}
        <ProfilePage {profile} {loadingProfile} error={profileError} onrefresh={loadProfile} ondeleteaccount={finishAccountDeletion} />
      {:else if route === '/account/change-password'}
        <PasswordRequestPage onrequest={requestPasswordChange} />
      {:else if route === '/account/change-email'}
        <EmailRequestPage currentEmail={profile?.email ?? ''} onrequest={requestEmailChange} />
      {/if}
      <footer class="page-footer"><span><ShieldCheck size={15} />接続は保護されています</span><span>DJ-MOO ACCOUNT</span></footer>
    </main>
  </div>
{:else}
  <main class="auth-shell">
    <section class="auth-aside">
      <a class="brand brand-light" href="/login" onclick={(event) => { event.preventDefault(); navigate('/login') }}>
        <span class="brand-mark">M</span><span><strong>DJ-MOO</strong><small>ACCOUNT CENTER</small></span>
      </a>
      <div class="auth-message">
        <span class="eyebrow">YOUR WORKSPACE, CONNECTED</span>
        <h1>ひとつのアカウントで、<br />組織とつながる。</h1>
        <p>組織ごとの役割とアクセスを、あなたのアカウントから確認できます。</p>
        <div class="auth-illustration" aria-hidden="true">
          <div class="orbit orbit-one"></div><div class="orbit orbit-two"></div>
          <div class="node node-main"><UserRound size={27} /></div>
          <div class="node node-org"><Building2 size={21} /></div>
          <div class="node node-role"><ShieldCheck size={20} /></div>
          <div class="connection connection-one"></div><div class="connection connection-two"></div>
          <span class="orbit-caption">MEMBER / ACCESS / TRUST</span>
        </div>
      </div>
      <div class="aside-foot"><span>SECURE BY DESIGN</span><span>01 / ACCOUNT</span></div>
    </section>
    <section class="auth-content">
      <div class="mobile-brand"><span class="brand-mark">M</span><strong>DJ-MOO</strong></div>
      {#if route === '/register'}
        <RegisterPage onregister={requestRegistration} onlogin={() => navigate('/login')} />
      {:else}
        <LoginPage onlogin={signIn} onregister={() => navigate('/register')} />
      {/if}
      <p class="auth-footnote">続行すると、アカウント利用規約とプライバシーポリシーに同意したものとみなされます。</p>
    </section>
  </main>
{/if}
