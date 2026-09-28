<script lang="ts">
  import { ArrowRight, Eye, EyeOff, LockKeyhole, Mail } from '@lucide/svelte'
  import { ApiError } from '../../shared/api'

  let { onlogin, onregister }: { onlogin: (email: string, password: string) => Promise<void>; onregister: () => void } = $props()
  let email = $state('')
  let password = $state('')
  let showPassword = $state(false)
  let busy = $state(false)
  let error = $state('')

  async function submit(event: SubmitEvent) {
    event.preventDefault()
    busy = true
    error = ''
    try {
      await onlogin(email, password)
    } catch (cause) {
      error = cause instanceof ApiError ? cause.message : 'ログインできませんでした。接続を確認して再度お試しください。'
    } finally {
      busy = false
    }
  }
</script>

<div class="auth-form-wrap">
  <div class="form-kicker">ACCOUNT ACCESS <span>01</span></div>
  <h2>おかえりなさい</h2>
  <p class="form-lead">登録したメールアドレスでログインしてください。</p>
  <form onsubmit={submit}>
    <label for="login-email">メールアドレス</label>
    <div class="input-wrap"><Mail size={18} /><input id="login-email" type="email" bind:value={email} autocomplete="email" placeholder="you@example.com" required /></div>
    <label for="login-password">パスワード</label>
    <div class="input-wrap"><LockKeyhole size={18} /><input id="login-password" type={showPassword ? 'text' : 'password'} bind:value={password} autocomplete="current-password" placeholder="パスワードを入力" required /><button class="input-action" type="button" onclick={() => showPassword = !showPassword} aria-label={showPassword ? 'パスワードを隠す' : 'パスワードを表示'} title={showPassword ? 'パスワードを隠す' : 'パスワードを表示'}>{#if showPassword}<EyeOff size={17} />{:else}<Eye size={17} />{/if}</button></div>
    {#if error}<p class="form-error" role="alert">{error}</p>{/if}
    <button class="primary-button" type="submit" disabled={busy}>{busy ? '確認しています…' : 'ログイン'}{#if !busy}<ArrowRight size={17} />{/if}</button>
  </form>
  <p class="switch-auth">アカウントをお持ちでない方は <button class="text-button" onclick={onregister}>新規登録</button></p>
  <div class="form-security"><LockKeyhole size={14} />認証情報は暗号化して送信されます</div>
</div>