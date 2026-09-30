# SecurityEvent 実装計画

## 目的

テナント境界を越えるアクセスを試みたユーザーを運営スタッフが調査し、必要に応じて手動でアカウント全体の退会処理を行える、staff 専用のセキュリティ対応機能を追加する。

対象の特定方法として、次の両方を提供する。

- テナント境界違反イベントの集計から、調査候補を見つける。
- 組織からの連絡などを受け、メールアドレスまたは UUID で個別にユーザーを検索する。

イベント回数だけで自動退会させず、staff が対象と理由を確認してから実行する。

## 現状

- `audit/models/security_event.py` に `SecurityEvent` と、イベント種別・ユーザー・対象組織・resource・IP・User-Agent・remarks 等のフィールドがある。
- 現状、コード内に `SecurityEvent.objects.create()` の呼び出しはなく、セキュリティイベントは記録されていない。
- `audit/views.py` は空であり、イベント閲覧・集計 API はない。
- 組織メンバーの HTTP API は組織単位の権限確認を行うが、拒否や組織不一致を SecurityEvent には記録していない。
- 招待トークンは URL の組織 slug と照合されるが、別組織の slug で使われた試行は記録されていない。
- `MembershipService` と `ProductService` にも同一組織の検証がある。ただし、これらの service は Request を受け取らず、Product の HTTP view も現時点ではないため、HTTP 要求者を特定するイベント記録の接続箇所は別途整理が必要。
- `DELETE /api/v1/auth/admin/delete-account/<uuid:user_id>/` は `IsAdminUser` で保護され、`AccountService.deactivate_account()` を呼び出す既存 API。退会処理には全 Membership の論理削除、ユーザーの匿名化・無効化、最後の組織 Admin の保護が含まれる。
- 現在のユーザープロフィール API は `is_staff` を返さず、フロントに staff 専用画面も全ユーザー検索 API もない。

## 実装ステップ

### 1. 違反イベントを記録する

- `SecurityEvent` を作成する監査サービスを追加する。
- イベント種別、行為ユーザー、対象組織・resource・resource ID、発生時刻、IP、User-Agent を記録する。
- 初期対象は、Request を受け取る境界拒否箇所とする。現時点で確認できた候補は、組織メンバー操作での権限不足・組織不一致と、招待トークンを異なる組織 slug で使用するケース。
- `MembershipService` / `ProductService` の Request 非依存な検証には Request 情報を無理に持ち込まない。対応する HTTP API が追加された時点で、その入口からイベントを記録する。

### 2. staff 専用の調査 API を追加する

- イベント集計 API を追加し、Django の `is_staff` に基づく `IsAdminUser` で保護する。
- staff が期間と最小イベント回数を指定し、条件に該当する調査候補を取得できるようにする。期間・回数の範囲にはサーバー側の上限を設ける。
- email は完全一致、UUID は ID 指定を基本とした staff 専用の個別ユーザー検索 API を追加する。
- API の返却情報は、対象特定に必要な ID、email、有効状態、所属組織/Admin 状態、最近の違反イベント概要に限定する。
- `UserProfileSerializer` に読み取り専用の `is_staff` を追加し、フロントで staff 導線を表示するために使う。これは表示上の制御であり、認可は必ず各 backend API で行う。

### 3. staff の全体退会を監査可能にする

- 既存の staff 専用 `DeleteAccountView` と `AccountService.deactivate_account()` を再利用する。
- staff に退会理由の入力を必須とし、実行者、対象者の退会前 ID/email、理由、処理結果を監査記録に残す。
- `SecurityEvent` を拡張する場合は staff 操作のイベント種別と実行者情報を追加し、必要な migration を作成する。対象ユーザーの匿名化後 email で元の識別情報を上書きしないよう、退会前のスナップショットを明示的に保存する。
- staff 自身を誤って退会対象にできないようにする。
- 最後の組織 Admin を退会させようとした場合の既存 `409 Conflict` を維持し、対象となる組織と理由を staff 画面に表示する。

### 4. staff 専用フロントエンドを追加する

- `App.svelte` に staff console の route と navigation を追加し、プロフィールの `is_staff` が true の場合だけリンクを表示する。
- staff でない利用者が staff route を直接開いた場合も通常画面へ戻す。ただし、route guard は利便性のためであり、backend 権限チェックの代わりにはしない。
- 画面に「違反イベントから候補を調査」と「email/UUID で個別検索」の二つの入口を設ける。
- イベント候補には集計条件（期間・最小回数）、対象組織、発生回数、最近のイベント概要を表示する。
- 退会前に、全組織からの退会・アカウント無効化と匿名化・取り消し不可であることを明示する。確認語と必須理由を入力してから既存 staff 退会 API を呼び出す。
- 成功時は結果一覧を更新する。最後の Admin による `409`、対象不在、権限エラー、通信エラーを区別して表示し、失敗を成功扱いしない。

### 5. テストと運用確認

- Backend: イベント作成時の actor・organization・target・IP/User-Agent、期間と件数による集計、email/UUID検索、non-staff 拒否、退会理由必須、実行者と対象スナップショットの監査、staff 自身の対象拒否、最後の Admin による `409`、退会成功時の匿名化と全 Membership 論理削除を検証する。
- Frontend: staff/non-staff のリンク表示と直接 route、イベント候補、個別検索、確認語・理由の必須、成功・`409`・`403` 表示を検証する。
- `python manage.py test audit.tests tenants.tests accounts.tests.test_account` を実行する。
- `npm --prefix frontend test`、`npm --prefix frontend run check`、`npm --prefix frontend run build` を実行する。
- 可能な範囲で PostgreSQL 上のイベント集計・退会連携を検証する。

## 主な関連ファイル

- `audit/models/security_event.py` — 既存イベントモデル。実行者/対象スナップショットと staff 操作監査の拡張候補。
- `audit/views.py` — staff 専用イベント集計 API。
- `audit/` — 監査イベント writer/service と migration の追加先。
- `tenants/views/membership_views.py` — Request がある組織メンバー境界拒否の記録。
- `tenants/views/invitation_views.py` — 組織 slug と招待 token の不一致記録。
- `tenants/services/membership_service.py` — Request 非依存の組織境界検証。HTTP 入口追加時に計測を接続。
- `products/services/product_service.py` — 同一組織検証。HTTP API 追加時の計測対象。
- `accounts/serializers/account_serializers.py` — `UserProfileSerializer.is_staff` と退会理由入力。
- `accounts/views/account_views.py` — staff 検索 API と理由付き全体退会。
- `accounts/urls.py` — staff 検索 API の route。
- `frontend/src/App.svelte` — staff route、navigation、プロフィールに基づく表示制御。
- `frontend/src/features/accounts/api.ts` — `is_staff` を含む profile 契約。
- `frontend/src/features/staff/` — staff 検索 API client と console UI の追加先。
- `config/api/v1/urls.py` — audit API を公開する場合の include。
- `tests/integration/` — DB 依存の監査・退会連携テストの配置候補。

## 決定事項

- 対象特定は違反イベント候補と email/UUID による個別検索の両方をサポートする。
- 回数・時間窓の運用値は未決定。staff が条件を指定できるようにし、集計結果はあくまで調査候補とする。閾値による自動退会はしない。
- 全体退会を実行できるのは Django `is_staff` を持つ運営担当のみ。組織 Admin による Membership 解除とは明確に分離する。
- 全体退会は取り消せない運営操作として、対象、実行者、理由を監査に残し、確認入力を必須にする。
- フロントの非表示・route guard は UI 上の制御にすぎず、認可境界は backend permission とする。

## 今後決めること

- 監視閾値、時間窓、候補集計の単位（ユーザー、IP、組織の組み合わせ）。
- SecurityEvent の保存期間と、IP/User-Agent の個人情報としての取り扱い。
- Reverse proxy 配下で信頼する転送 IP header と、その設定方法。
- Request を受け取らない service 層の検証を、将来 API 化する際にどの入口で記録するか。
