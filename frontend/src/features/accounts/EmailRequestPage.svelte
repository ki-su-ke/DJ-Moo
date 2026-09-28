<script lang="ts">
  import { ArrowLeft, Mail, Send } from '@lucide/svelte'
  import { ApiError } from '../../shared/api'

  let { currentEmail, onrequest }: { currentEmail: string; onrequest: (email: string) => Promise<{ message: string }> } = $props()
  let newEmail = $state('')
  let busy = $state(false)
  let error = $state('')
  let message = $state('')

  async function submit(event: SubmitEvent) {
    event.preventDefault()
    busy = true
    error = ''
    message = ''
    try {
      message = (await onrequest(newEmail)).message
    } catch (cause) {
      error = cause instanceof ApiError ? cause.message : 'リクエストを送信できませんでした。'
    } finally {
      busy = false
    }
  }
</script>

<section class="content-wrap narrow-content">
  <a class="back-link" href="/profile"><ArrowLeft size={16} />プロフィールに戻る</a>
  <div class="page-heading"><div><div class="section-kicker">PERSONAL / CONTACT</div><h1>メールアドレス変更</h1><p>新しいアドレスに確認リンクを送信します。</p></div></div>
  <section class="profile-panel request-panel"><div class="panel-title"><span class="panel-icon"><Mail size={18} /></span><div><h2>確認先アドレス</h2><p>現在の登録先: {currentEmail || '読み込み中'}</p></div></div><form onsubmit={submit}><label for="new-email">新しいメールアドレス</label><div class="input-wrap"><Mail size={18} /><input id="new-email" type="email" bind:value={newEmail} autocomplete="email" placeholder="new@example.com" required /></div><p class="request-copy">新しいアドレスに届くリンクで確定するまで、登録アドレスは変わりません。</p>{#if error}<p class="form-error" role="alert">{error}</p>{/if}{#if message}<p class="form-success" role="status"><Send size={16} />{message}</p>{/if}<button class="primary-button" type="submit" disabled={busy}>{busy ? '送信しています…' : '確認メールを送信'}{#if !busy}<Send size={16} />{/if}</button></form></section>
</section>