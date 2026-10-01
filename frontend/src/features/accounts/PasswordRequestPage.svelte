<script lang="ts">
  import { ArrowLeft, KeyRound, Send } from '@lucide/svelte'
  import { ApiError } from '../../shared/api'

  let { onrequest }: { onrequest: () => Promise<{ message: string }> } = $props()
  let busy = $state(false)
  let error = $state('')
  let message = $state('')

  async function submit() {
    busy = true
    error = ''
    message = ''
    try {
      message = (await onrequest()).message
    } catch (cause) {
      error = cause instanceof ApiError ? cause.message : 'リクエストを送信できませんでした。'
    } finally {
      busy = false
    }
  }
</script>

<section class="content-wrap narrow-content">
  <a class="back-link" href="/profile"><ArrowLeft size={16} />プロフィールに戻る</a>
  <div class="page-heading"><div><div class="section-kicker">PERSONAL / SECURITY</div><h1>パスワード変更</h1><p>確認リンクを登録メールアドレスへ送信します。</p></div></div>
  <section class="profile-panel request-panel"><div class="panel-title"><span class="panel-icon"><KeyRound size={18} /></span><div><h2>変更用リンクを送信</h2><p>リンクの有効期限は1時間です。</p></div></div><p class="request-copy">メール内のリンクを開き、新しいパスワードを設定してください。安全のため、リンクを開くだけではパスワードは変更されません。</p>{#if error}<p class="form-error" role="alert">{error}</p>{/if}{#if message}<p class="form-success" role="status"><Send size={16} />{message}</p>{/if}<button class="primary-button" onclick={submit} disabled={busy}>{busy ? '送信しています…' : '変更メールを送信'}{#if !busy}<Send size={16} />{/if}</button></section>
</section>