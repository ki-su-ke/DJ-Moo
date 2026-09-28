<script lang="ts">
  import { ArrowRight, Mail, Send } from '@lucide/svelte'
  import { ApiError } from '../../shared/api'

  let { onregister, onlogin }: { onregister: (email: string) => Promise<{ message: string }>; onlogin: () => void } = $props()
  let email = $state('')
  let busy = $state(false)
  let error = $state('')
  let sent = $state(false)

  async function submit(event: SubmitEvent) {
    event.preventDefault()
    busy = true
    error = ''
    try {
      await onregister(email)
      sent = true
    } catch (cause) {
      error = cause instanceof ApiError ? cause.message : 'メールを送信できませんでした。時間をおいて再度お試しください。'
    } finally {
      busy = false
    }
  }
</script>

<div class="auth-form-wrap">
  <div class="form-kicker">CREATE ACCOUNT <span>02</span></div>
  {#if sent}
    <div class="success-stamp"><Send size={20} /></div>
    <h2>メールを確認してください</h2>
    <p class="form-lead"><strong>{email}</strong> 宛てに認証リンクを送信しました。リンクを開くと登録を続けられます。</p>
    <button class="secondary-button full-button" onclick={onlogin}>ログイン画面へ戻る</button>
  {:else}
    <h2>アカウントを作成</h2>
    <p class="form-lead">メールアドレスを登録して、認証リンクを受け取ります。</p>
    <form onsubmit={submit}>
      <label for="register-email">メールアドレス</label>
      <div class="input-wrap"><Mail size={18} /><input id="register-email" type="email" bind:value={email} autocomplete="email" placeholder="you@example.com" required /></div>
      {#if error}<p class="form-error" role="alert">{error}</p>{/if}
      <button class="primary-button" type="submit" disabled={busy}>{busy ? '送信しています…' : '認証メールを送信'}{#if !busy}<ArrowRight size={17} />{/if}</button>
    </form>
    <p class="switch-auth">すでにアカウントをお持ちの方は <button class="text-button" onclick={onlogin}>ログイン</button></p>
  {/if}
  <div class="form-security"><Mail size={14} />登録完了とパスワード設定はメール内の画面で行います</div>
</div>